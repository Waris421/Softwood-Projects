import pandas as pd
import numpy as np

from datetime import timedelta
from collections import Counter
from typing import List
from math import ceil
import os

from django.db import transaction
from django.db.models import DateTimeField, Q, Sum
from django.db.models.functions import TruncDate, Cast, TruncMonth
from django.conf import settings

from .. import models
from core.services.generic_services import dfToListOfDicts, convertCountryNameToCode, convertCountryCodeToName
from core.services.generic_services import formatNumbers, convertMonthstoStrtEndDates
from core.constants.generic import TODAY

def convertHSCodeToCategory(HSCode: str):
    categoryMap = {
        '62': 'Woven',
        '61': 'Knit',
    }
    return categoryMap.get(HSCode[:2], 'Other')

def convertCategoryToHSCodeStart(categories: List[str]) -> List[str]:
    categoryMap = {
        'Woven': '62',
        'Knit': '61',
    }

    hsCodes = []
    for category in categories:
        if category in categoryMap:
            hsCodes.append(categoryMap[category])

    return list(set(hsCodes))

def ExtractUploadedData(dataFile):
    if str(dataFile.name).endswith(('.xls', '.xlsx')):
        dfUploadedData = pd.read_excel(dataFile)
    else:
        dfUploadedData = pd.read_csv(dataFile)
    del dataFile

    requiredCols = [
        'Origin', 'Importer', 'Exporter', 'SB Date', 'Quantity', 'Price', 'Currency', 'HSCode', 'Description'
    ]
    missingCols = [col for col in requiredCols if col not in dfUploadedData.columns]
    if missingCols:
        raise ValueError(f"The following Colums are missing in the data: {missingCols}")

    dfUploadedData = dfUploadedData[requiredCols]
    dfUploadedData.rename(inplace=True, columns={'Origin':'Country', 'SB Date':'ShipDate'})

    dfUploadedData['Country'] = dfUploadedData['Country'].str.strip()
    countryCodes = convertCountryNameToCode(dfUploadedData['Country'])
    dfUploadedData['Country'] = dfUploadedData['Country'].map(countryCodes)

    dfUploadedData['ShipDate'] = dfUploadedData['ShipDate'].dt.strftime('%Y-%m-%d')

    newEntries = []
    for _, row in dfUploadedData.iterrows():
        newEntry = models.ExportDataDraft(**row.to_dict())
        newEntries.append(newEntry)
    models.ExportDataDraft.objects.bulk_create(newEntries, batch_size=7000)

def GetPendingUploads():
    fields = ['ShipDate','Quantity','Price','HSCode','Description']
    pendingUploads = models.ExportDataDraft.objects.all().values(*fields)
    dfPendingUploads = pd.DataFrame(pendingUploads) if pendingUploads else pd.DataFrame(columns=fields)
    del pendingUploads

    if dfPendingUploads.empty:
        raise LookupError('Cannot find entries to approve.')
    
    dfPendingUploads['ShipDate'] = pd.to_datetime(dfPendingUploads['ShipDate'])

    addedMonths = models.ExportData.objects.annotate(
        ShipDatetime=Cast('ShipDate', output_field=DateTimeField()),
        ShipMonth=TruncDate('ShipDatetime', kind='month')
    ).values_list('ShipMonth', flat=True).distinct()
    addedMonths = [month.strftime('%b-%y') for month in addedMonths if month]
    addedMonths = set(addedMonths)

    summaryDict = {}
    uniqueMonths = dfPendingUploads['ShipDate'].dt.strftime('%b-%y').unique()
    summaryDict['months'] = ", ".join(sorted(uniqueMonths))

    summaryDict['totalQty'] = float(dfPendingUploads['Quantity'].sum())
    summaryDict['Price'] = float(dfPendingUploads['Price'].mean())
    summaryDict['numberOfEntries'] = len(dfPendingUploads)

    hsCodeCounts = Counter(dfPendingUploads['HSCode'])
    if hsCodeCounts:
        summaryDict['frequentHSCode'] = hsCodeCounts.most_common(1)[0][0]
    else:
        summaryDict['frequentHSCode'] = None

    itemDescriptionCounts = Counter(dfPendingUploads['Description'])
    if itemDescriptionCounts:
        summaryDict['frequentItem'] = itemDescriptionCounts.most_common(1)[0][0]
    else:
        summaryDict['frequentItem'] = None

    return summaryDict, addedMonths

def ConfirmPendingUploads(approval: str):
    if not approval:
        raise ValueError('Invalid Input')
    
    with transaction.atomic():
        pendingUploads = models.ExportDataDraft.objects.all()

        if approval == 'approve':
            dataToAdd = []
            for pendingUpload in pendingUploads:
                exportData = models.ExportData(
                    Country = pendingUpload.Country,
                    Exporter = pendingUpload.Exporter,
                    ShipDate = pendingUpload.ShipDate,
                    Importer = pendingUpload.Importer,
                    Quantity = pendingUpload.Quantity,
                    Price = pendingUpload.Price,
                    Currency = pendingUpload.Currency,
                    HSCode = pendingUpload.HSCode,
                    Description = pendingUpload.Description
                )
                dataToAdd.append(exportData)
            
            if dataToAdd:
                models.ExportData.objects.bulk_create(dataToAdd)
        pendingUploads.delete()

def GetMonthWiseQty():
    fields = ['Month', 'Quantity', 'Checked']
    exportData = models.ExportData.objects.annotate(Month=TruncMonth('ShipDate')
                                                    ).values('Month').annotate(
                                                        Quantity=Sum('Quantity',
                                                        )).order_by('Month')
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData, fields

    last12Months = TODAY - timedelta(days=365)
    dfExportData['Checked'] = dfExportData['Month'] >= last12Months.date()

    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers)
    dfExportData['Month'] = pd.to_datetime(dfExportData['Month']).dt.strftime('%b-%Y')

    return dfToListOfDicts(dfExportData)

def GetCountrySummary(months: List[str], importers: List[str], exporters: List[str], categories: List[str]):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if importers:
        filters &= Q(Importer__in=importers)
    
    if exporters:
        filters &= Q(Exporter__in=exporters)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)
    
    
    fields = ['Country','Quantity']
    exportData = models.ExportData.objects.filter(filters).values('Country').annotate(Quantity=Sum('Quantity'))
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData, fields

    filePath = os.path.join(settings.BASE_DIR, 'static/Country-Codes-Location.json')
    dfCoordinates = pd.read_json(filePath)

    dfExportData = pd.merge(left=dfExportData, right=dfCoordinates, left_on='Country', right_on='alpha2', how='left')
    del dfCoordinates

    dfExportData.drop(inplace=True, columns=['alpha2', 'alpha3', 'numeric'])
    dfExportData.rename(inplace=True, columns={'Country':'CountryCode','country': 'CountryName'}) 

    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)

    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers)    

    return dfToListOfDicts(dfExportData)

def GetCategorySummary(months: List[str]):
    startDate, endDate = convertMonthstoStrtEndDates(months)  
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    fields = ['HSCode','Quantity']
    exportData = models.ExportData.objects.filter(filters).values('HSCode').annotate(Quantity=Sum('Quantity'))
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData

    dfExportData['Category'] = dfExportData['HSCode'].apply(convertHSCodeToCategory)
    dfExportData.drop(columns=['HSCode'], inplace=True)

    dfExportData = dfExportData.groupby('Category').agg({'Quantity': 'sum'}).reset_index()
    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)
    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers) 

    return dfToListOfDicts(dfExportData)

def GetImporterSummary(months: List[str], countries: List[str], exporters: List[str], categories: List[str]):
    startDate, endDate = convertMonthstoStrtEndDates(months)    
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if exporters:
        filters &= Q(Exporter__in=exporters)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    fields = ['Importer','Quantity']
    exportData = models.ExportData.objects.filter(filters).values('Importer').annotate(Quantity=Sum('Quantity'))
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData,fields

    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)
    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers) 

    return dfToListOfDicts(dfExportData)

def GetExporterSummary(months: List[str], countries: List[str], importers: List[str], categories: List[str]):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importers:
        filters &= Q(Importer__in=importers)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    fields = ['Exporter','Quantity']
    exportData = models.ExportData.objects.filter(filters).values('Exporter').annotate(Quantity=Sum('Quantity'))
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData,fields

    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)

    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers) 

    return dfToListOfDicts(dfExportData)

def GetDetailsTable(months: List[str], countries: List[str], exporters: List[str], importers: List[str], categories: List[str], page: str):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importers:
        filters &= Q(Importer__in=importers)
    
    if exporters:
        filters &= Q(Exporter__in=exporters)
    
    itemsPerPage = 10
    pageNum = int(page)
    offset = (pageNum - 1) * itemsPerPage
    limit = offset + itemsPerPage
    
    fields = ['ShipDate', 'Importer', 'Exporter', 'Description', 'Quantity', 'Price']
    exportData = models.ExportData.objects.filter(filters).order_by('-ShipDate', '-Quantity')

    numberOfPages = ceil(exportData.count() / itemsPerPage)
    
    exportData = exportData.values(*fields)[offset:limit]
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData, fields

    dfExportData.sort_values(by=['ShipDate', 'Quantity'], ascending=[False, False], inplace=True)

    dfExportData['Month'] = pd.to_datetime(dfExportData['ShipDate']).dt.strftime('%b-%Y')
    dfExportData.drop(inplace=True, columns=['ShipDate'])

    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers)
    
    return dfToListOfDicts(dfExportData), numberOfPages