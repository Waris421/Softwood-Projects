import pandas as pd
import numpy as np

from datetime import timedelta, datetime
from collections import Counter
from typing import List
from math import ceil
import os

from django.db import transaction
from django.db.models import Q, Sum, Subquery, F, ExpressionWrapper, DecimalField, Min, Max
from django.db.models.functions import TruncMonth
from django.conf import settings

from .. import models
from core.services.generic_services import dfToListOfDicts, convertCountryNameToCode, updateModelWithDF
from core.services.generic_services import formatNumbers, convertMonthstoStrtEndDates, askAI, convertCountryCodeToName
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

def CalculateChecks(
        months: List[str], importers: List[str], exporters: List[str], categories: List[str], countries: List[str]
):
    checks = {
        'month': 'checked' if months else '',
        'importer': 'checked' if importers else '',
        'exporter': 'checked' if exporters else '',
        'category': 'checked' if categories else '',
        'country': 'checked' if countries else '',
    }

    return checks

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
    try:
        countryCodes = convertCountryNameToCode(dfUploadedData['Country'])
    except Exception as e:
        raise ValueError(e)

    for countryName, countryCode in countryCodes.items():
        if not countryCode:
            raise ValueError(f'Invalid Country Name: {countryName}')

    dfUploadedData['Country'] = dfUploadedData['Country'].map(countryCodes)

    #Clean the empty spaces etch from the data
    columnsToClean = ['Importer', 'Exporter']
    for col in columnsToClean:
        dfUploadedData[col] = dfUploadedData[col].str.replace(r'(_x000D_|\n|\t)', '', regex=True)
        dfUploadedData[col] = dfUploadedData[col].str.rstrip('`., ')
        dfUploadedData[col] = dfUploadedData[col].str.strip()
    

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
        shipMonth=TruncMonth('ShipDate')
    ).values('shipMonth').distinct().order_by('shipMonth')
    addedMonths = [item['shipMonth'] for item in addedMonths]
    addedMonths = [month.strftime('%b-%y') for month in addedMonths]
    addedMonths = ", ".join(addedMonths)

    summaryDict = {}
    uniqueMonths = dfPendingUploads['ShipDate'].dt.strftime('%b-%y').unique()
    summaryDict['months'] = ", ".join(sorted(uniqueMonths))

    summaryDict['totalQty'] = formatNumbers(float(dfPendingUploads['Quantity'].sum()))
    summaryDict['Price'] = formatNumbers(float(dfPendingUploads['Price'].mean()))
    summaryDict['numberOfEntries'] = formatNumbers(len(dfPendingUploads))

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

def GetMonthWiseQty(
        selectedMonths: List[str], countries: List[str], importerAliases: List[str],
        exporterAliases: List[str],
):    
    filters = Q()
    if countries:
        filters &= Q(Country__in=countries)
    
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    fields = ['Month', 'Quantity', 'Checked']    
    exportData = models.ExportData.objects.filter(filters).annotate(
        Month=TruncMonth('ShipDate')
    ).values('Month').annotate(
        Quantity=Sum('Quantity')
    ).order_by('-Month')
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData, fields

    if selectedMonths:
        selectedMonthDates = set()
        for monthStr in selectedMonths:
            try:
                dateObj = datetime.strptime(monthStr, '%b-%Y').date()
                selectedMonthDates.add(dateObj)
            except ValueError:
                continue
        
        dfExportData['Checked'] = dfExportData['Month'].isin(selectedMonthDates)
    else:
        last12Months = TODAY - timedelta(days=365)
        dfExportData['Checked'] = dfExportData['Month'] >= last12Months.date()

    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers)
    dfExportData['Month'] = pd.to_datetime(dfExportData['Month']).dt.strftime('%b-%Y')

    return dfToListOfDicts(dfExportData)

def GetCountrySummary(
        months: List[str], importerAliases: List[str], exporterAliases: List[str], categories: List[str], countries: List[str], search: str|None,
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)
    
    if search:
        filters &= Q(Country__icontains=search)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)
    
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
    
    dfExportData[['CountryName', 'latitude', 'longitude']] = dfExportData[['CountryName', 'latitude', 'longitude']].fillna('')

    #Sort w.r.t qty first
    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)
    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers)    

    #Bring the selected countries to the top
    dfExportData['SortKey'] = dfExportData['CountryCode'].apply(lambda x: 0 if x in countries else 1)
    dfExportData.sort_values(by='SortKey', kind='stable', inplace=True)
    dfExportData.drop(inplace=True, columns=['SortKey'])

    return dfToListOfDicts(dfExportData)

def GetCategorySummary(
        months: List[str], importerAliases: List[str], exporterAliases: List[str], countries: List[str],
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)  
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)

    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)

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

def GetImporterSummary(
        months: List[str], countries: List[str], exporterAliases: List[str], categories: List[str], importers: List[str], search: str|None,
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)    
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)
    
    if search:
        importerNames = models.ImporterAlias.objects.filter(Name__icontains=search).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__icontains=search)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)

    fields = ['Importer','Quantity', 'ShipmentValue']
    exportData = models.ExportData.objects.filter(filters).annotate(
        ShipmentValue=ExpressionWrapper(F('Quantity') * F('Price'), output_field=DecimalField())
    ).values('Importer').annotate(
        Quantity=Sum('Quantity'),
        ShipmentValue=Sum('ShipmentValue')
    )
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData

    fields = ['Name', 'Alias']
    importerAliases = models.ImporterAlias.objects.filter(Name__in=dfExportData['Importer'].to_list()).values(*fields)
    dfImporterAliases = pd.DataFrame(importerAliases) if importerAliases else pd.DataFrame(columns=fields)
    del importerAliases, fields
    
    dfExportData = pd.merge(left=dfExportData, right=dfImporterAliases, left_on='Importer', right_on='Name', how='left')
    del dfImporterAliases
    dfExportData.drop(inplace=True, columns='Name')

    dfExportData['Importer'] = np.where(dfExportData['Alias'].isna(), dfExportData['Importer'], dfExportData['Alias'])
    dfExportData.drop(inplace=True, columns=['Alias'])

    dfExportData = dfExportData.groupby('Importer').agg({'Quantity': 'sum', 'ShipmentValue': 'sum'}).reset_index()
    
    dfExportData['Price'] = (dfExportData['ShipmentValue'].astype(float) / dfExportData['Quantity']).round(2)
    dfExportData.drop(inplace=True, columns=['ShipmentValue'])

    #Sort w.r.t qty first
    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)
    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers) 

    #Bring the selected importers to the top
    dfExportData['SortKey'] = dfExportData['Importer'].apply(lambda x: 0 if x in importers else 1)
    dfExportData.sort_values(by='SortKey', kind='stable', inplace=True)
    dfExportData.drop(inplace=True, columns=['SortKey'])

    #select the first 50 rows only
    dfExportData = dfExportData.head(50)

    return dfToListOfDicts(dfExportData)

def GetExporterSummary(
        months: List[str], countries: List[str], importerAliases: List[str], categories: List[str], exporters: List[str], search: str|None,
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)
    if search:
        exporterNames = models.ExporterAlias.objects.filter(Name__icontains=search).values_list('Name', flat=True)
        filters &= Q(Exporter__in=exporterNames) | Q(Exporter__icontains=search)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)

    fields = ['Exporter','Quantity']
    exportData = models.ExportData.objects.filter(filters).values('Exporter').annotate(Quantity=Sum('Quantity'))
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)
    del exportData,fields

    fields = ['Name', 'Alias']
    exporterAliases = models.ExporterAlias.objects.filter(Name__in=dfExportData['Exporter'].to_list()).values(*fields)
    dfExporterAliases = pd.DataFrame(exporterAliases) if exporterAliases else pd.DataFrame(columns=fields)
    del exporterAliases, fields
    
    dfExportData = pd.merge(left=dfExportData, right=dfExporterAliases, left_on='Exporter', right_on='Name', how='left')
    del dfExporterAliases
    dfExportData.drop(inplace=True, columns='Name')

    dfExportData['Exporter'] = np.where(dfExportData['Alias'].isna(), dfExportData['Exporter'], dfExportData['Alias'])
    dfExportData.drop(inplace=True, columns=['Alias'])

    dfExportData = dfExportData.groupby('Exporter').agg({'Quantity': 'sum'}).reset_index()

    #sort w.r.t. country first
    dfExportData.sort_values(by='Quantity', ascending=False, inplace=True)
    dfExportData['Quantity'] = dfExportData['Quantity'].apply(formatNumbers) 

    #Bring the selected exporters to the top
    dfExportData['SortKey'] = dfExportData['Exporter'].apply(lambda x: 0 if x in exporters else 1)
    dfExportData.sort_values(by='SortKey', kind='stable', inplace=True)
    dfExportData.drop(inplace=True, columns=['SortKey'])

    #Select the frist 50 rows only
    dfExportData = dfExportData.head(50)

    return dfToListOfDicts(dfExportData)

def GetDetailsTable(
        months: List[str], countries: List[str], exporterAliases: List[str], importerAliases: List[str], categories: List[str], page: str,
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)
    
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

def GetStats(
        months: List[str], countries: List[str], exporterAliases: List[str], importerAliases: List[str], categories: List[str],
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    if exporterAliases:
        ExporterNames = models.ExporterAlias.objects.filter(Alias__in=exporterAliases).values_list('Name', flat=True)
        filters &= Q(Exporter__in=ExporterNames) | Q(Exporter__in=exporterAliases)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)

    instances = models.ExportData.objects.filter(filters)

    totalQuantity = instances.aggregate(TotalQuantity=Sum('Quantity'))['TotalQuantity']

    totalValue = instances.aggregate(total_v=Sum(F('Quantity') * F('Price'), output_field=DecimalField()))['total_v']
    
    averagePrice = float(totalValue)/totalQuantity

    totalQuantity = formatNumbers(totalQuantity)
    averagePrice = round(averagePrice, 2)

    result = {
        'quantity': totalQuantity,
        'price': averagePrice
    }

    return result

def GetSliderParamters(
        months: List[str], countries: List[str], exporters: List[str], importerAliases: List[str], categories: List[str]
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    if exporters:
        filters &= Q(Exporter__in=exporters)
    fields = {'Quantity', 'Price'}
    exportData = models.ExportData.objects.filter(filters).values(*fields)
    dfExportdata = pd.DataFrame(exportData)
    del exportData

    result = {
        'minQty': 0,
        'maxQty': 0,
        'minPrice': 0,
        'maxPrice': 0
    }

    if dfExportdata.empty:
        return result

    result['minQty'] = round(dfExportdata['Quantity'].min())
    result['maxQty'] = round(dfExportdata['Quantity'].max())
    result['minPrice'] = round(dfExportdata['Price'].min())
    result['maxPrice'] = round(dfExportdata['Price'].max())

    return result

def DownLoadExportData(
        months: List[str], countries: List[str], exporters: List[str], importerAliases: List[str], categories: List[str],
        minQty: str|None, maxQty:str|None, minPrice:str|None, maxPrice:str|None
):
    startDate, endDate = convertMonthstoStrtEndDates(months)
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)

    if countries:
        filters &= Q(Country__in=countries)
    if importerAliases:
        importerNames = models.ImporterAlias.objects.filter(Alias__in=importerAliases).values_list('Name', flat=True)
        filters &= Q(Importer__in=importerNames) | Q(Importer__in=importerAliases)
    
    if categories:
        HSCodes = convertCategoryToHSCodeStart(categories)
        for HSCode in HSCodes:
            filters &= Q(HSCode__startswith=HSCode)

    if exporters:
        filters &= Q(Exporter__in=exporters)
    
    if minQty:
        filters &= Q(Quantity__gte=minQty)
    if maxQty:
        filters &= Q(Quantity__lte=maxQty)
    if minPrice:
        filters &= Q(Price__gte=minPrice)
    if maxPrice:
        filters &= Q(Price__lte=maxPrice)
    
    fields = ['Country', 'Exporter', 'ShipDate', 'Importer', 'Quantity', 'Price', 'Currency', 'HSCode', 'Description']
    exportData = models.ExportData.objects.filter(filters).values(*fields)
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)

    dfExportData['Country'] = dfExportData['Country'].apply(convertCountryCodeToName)

    return dfExportData

def GetImportersForRefinement(filterMethod: str|None, search: str|None):
    QUERY_LIMIT = 20
    
    hasFilters = False
    filters = Q()

    aliases = models.ImporterAlias.objects.values_list('Name', flat=True)
    if filterMethod == 'pending':
        filters &= ~Q(Importer__in=Subquery((aliases)))
        hasFilters = True
    elif filterMethod == 'previous':
        filters &= Q(Importer__in=Subquery((aliases)))
        hasFilters = True
    
    if search:
        filters &= Q(Importer__icontains=search)
        hasFilters = True

    if not hasFilters:
        return [], None, None
    del hasFilters

    fields = ['Importer']
    importerNames = models.ExportData.objects.filter(filters).values(*fields).distinct()
    dfImporterNames = pd.DataFrame(importerNames) if importerNames else pd.DataFrame(columns=fields)
    del importerNames, filters

    fields = ['Name','Alias']
    aliases = models.ImporterAlias.objects.all().values(*fields)
    dfImporterAliases = pd.DataFrame(aliases) if aliases else pd.DataFrame(columns=fields)
    del aliases, fields
   
    addedAliases = dfImporterAliases['Alias'].to_list()

    dfImporterNames = pd.merge(left=dfImporterNames, right=dfImporterAliases, left_on='Importer', right_on='Name', how='left')
    del dfImporterAliases
    dfImporterNames.drop(inplace=True, columns=['Name'])

    totalDataLength = len(dfImporterNames)
    
    numberOfSamples = min(QUERY_LIMIT, totalDataLength)
    dfImporterNames = dfImporterNames.sample(n=numberOfSamples).reset_index(drop=True)

    unAliasedImporters = dfImporterNames[dfImporterNames['Alias'].isna()]['Importer'].to_list()
    
    if unAliasedImporters:
        prompt = f"""
                Given the following company names, provide a single, standardized name.

                **Existing Aliases to Use:**
                {addedAliases}

                **Instructions:**
                1. Check if any of the provided company names are a direct match or a clear alias of a name in the "Existing Aliases to Use" list.
                2. If a match is found, use the corresponding alias from the list as the "SimplifiedName."
                3. If no match is found, create a new "SimplifiedName." For this new name, ensure only the first letter of each word is capitalized,
                and remove common legal suffixes like Ltd, LLC, Inc, GmbH, Co., corp etc.
                4. If the "Existing Aliases to Use" list is empty, always follow Instruction #3.
                5. Be concise and respond only with the name.

                **Company Names to Standardize:**
                {unAliasedImporters}
                """

        del unAliasedImporters, addedAliases
        
        responseSchema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "Importer": {"type": "STRING"},
                    "SimplifiedName": {"type": "STRING"}
                },
                "required": ["Importer", "SimplifiedName"]
            }
        }
        try:
            suggestions = askAI(prompt, responseSchema)
        except Exception as e:
            raise ValueError(e)
        del prompt, responseSchema

        dfSuggestions = pd.DataFrame(suggestions) if suggestions else pd.DataFrame(columns=['Importer', 'SimplifiedName'])
        del suggestions
        
        dfImporterNames = pd.merge(left=dfImporterNames, right=dfSuggestions, on='Importer', how='left')
        del dfSuggestions
        
        dfImporterNames['Alias'] = np.where(dfImporterNames['Alias'].isna(), dfImporterNames['SimplifiedName'], dfImporterNames['Alias'])
        dfImporterNames.drop(inplace=True, columns=['SimplifiedName'])

    return dfToListOfDicts(dfImporterNames), numberOfSamples, totalDataLength

def GetExportersForRefinement(filterMethod: str|None, search: str|None):
    QUERY_LIMIT = 20
    
    hasFilters = False
    filters = Q()

    aliases = models.ExporterAlias.objects.values_list('Name', flat=True)
    if filterMethod == 'pending':
        filters &= ~Q(Exporter__in=Subquery((aliases)))
        hasFilters = True
    elif filterMethod == 'previous':
        filters &= Q(Exporter__in=Subquery((aliases)))
        hasFilters = True
    
    if search:
        filters &= Q(Exporter__icontains=search)
        hasFilters = True
    
    if not hasFilters:
        return [], None, None
    del hasFilters

    fields = ['Exporter']
    exporterNames = models.ExportData.objects.filter(filters).values(*fields).distinct()
    dfExporterNames = pd.DataFrame(exporterNames) if exporterNames else pd.DataFrame(columns=fields)
    del exporterNames, filters

    fields = ['Name','Alias']
    aliases = models.ExporterAlias.objects.all().values(*fields)
    dfExporterAliases = pd.DataFrame(aliases) if aliases else pd.DataFrame(columns=fields)
    del aliases, fields

    addedAliases = dfExporterAliases['Alias'].to_list()

    dfExporterNames = pd.merge(left=dfExporterNames, right=dfExporterAliases, left_on='Exporter', right_on='Name', how='left')
    del dfExporterAliases
    dfExporterNames.drop(inplace=True, columns=['Name'])
    
    totalDataLength = len(dfExporterNames)
    
    numberOfSamples = min(QUERY_LIMIT, totalDataLength)
    dfExporterNames = dfExporterNames.sample(n=numberOfSamples).reset_index(drop=True)

    unAliasedExporters = dfExporterNames[dfExporterNames['Alias'].isna()]['Exporter'].to_list()
    
    if unAliasedExporters:
        prompt = f"""
                Given the following company names, provide a single, standardized name.

                **Existing Aliases to Use:**
                {addedAliases}

                **Instructions:**
                1. Check if any of the provided company names are a direct match or a clear alias of a name in the "Existing Aliases to Use" list.
                2. If a match is found, use the corresponding alias from the list as the "SimplifiedName."
                3. If no match is found, create a new "SimplifiedName." For this new name, ensure only the first letter of each word is capitalized,
                and remove common legal suffixes like Ltd, LLC, Inc, GmbH, Co., corp etc.
                4. If the "Existing Aliases to Use" list is empty, always follow Instruction #3.
                5. Be concise and respond only with the name.

                **Company Names to Standardize:**
                {unAliasedExporters}
                """

        del unAliasedExporters, addedAliases

        responseSchema = {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "Exporter": {"type": "STRING"},
                    "SimplifiedName": {"type": "STRING"}
                },
                "required": ["Exporter", "SimplifiedName"]
            }
        }
        try:
            suggestions = askAI(prompt, responseSchema)
        except Exception as e:
            raise ValueError(e)
        del prompt, responseSchema
        
        dfSuggestions = pd.DataFrame(suggestions) if suggestions else pd.DataFrame(columns=['Importer', 'SimplifiedName'])
        del suggestions

        dfExporterNames = pd.merge(left=dfExporterNames, right=dfSuggestions, on='Exporter', how='left')
        del dfSuggestions

        dfExporterNames['Alias'] = np.where(dfExporterNames['Alias'].isna(), dfExporterNames['SimplifiedName'], dfExporterNames['Alias'])
        dfExporterNames.drop(inplace=True, columns=['SimplifiedName'])

    return dfToListOfDicts(dfExporterNames), numberOfSamples, totalDataLength

def SaveImportersAlias(dfAliases: pd.DataFrame):
    fields = ['id', 'Name']
    previousData = models.ImporterAlias.objects.filter(Name__in=dfAliases['Importer'].to_list()).values(*fields)
    dfPreviousData = pd.DataFrame(previousData) if previousData else pd.DataFrame(columns=fields)
    del previousData, fields
    
    dfAliases.rename(inplace=True, columns={'Importer':'Name'})
    
    dfAliases = pd.merge(left=dfAliases, right=dfPreviousData, on='Name', how='left')
    
    try:
        updateModelWithDF(models.ImporterAlias, dfAliases, dfPreviousData)
    except Exception as e:
        raise ValueError(e)

def SaveExportersAlias(dfAliases: pd.DataFrame):
    fields = ['id', 'Name']
    previousData = models.ExporterAlias.objects.filter(Name__in=dfAliases['Exporter'].to_list()).values(*fields)
    dfPreviousData = pd.DataFrame(previousData) if previousData else pd.DataFrame(columns=fields)
    del previousData, fields

    dfAliases.rename(inplace=True, columns={'Exporter':'Name'})

    dfAliases = pd.merge(left=dfAliases, right=dfPreviousData, on='Name', how='left')
    
    try:
        updateModelWithDF(models.ExporterAlias, dfAliases, dfPreviousData)
    except Exception as e:
        raise ValueError(e)