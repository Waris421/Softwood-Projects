import pandas as pd

from datetime import date, timedelta
from collections import Counter

from django.db import transaction
from django.db.models import DateTimeField, Q
from django.db.models.functions import TruncDate, Cast

from django_countries import countries

from .. import models
from core.services.generic_services import dfToListOfDicts, convertCountryNameToCode, convertCountryCodeToName

def getExportData(startDateStr: str, endDateStr: str, country: str):
    today = date.today()
    firstDayOfCurrentMonth = date(today.year, today.month, 1)
    if startDateStr:
        startDate = date.fromisoformat(startDateStr)
    else:
        lastDayOfPreviousMonth = firstDayOfCurrentMonth - timedelta(days=1)
        startDate = date(lastDayOfPreviousMonth.year, lastDayOfPreviousMonth.month, 1)
    
    if endDateStr:
        endDate = date.fromisoformat(endDateStr)
    else:
        endDate = firstDayOfCurrentMonth - timedelta(days=1)
    
    filters = Q(ShipDate__gte=startDate, ShipDate__lte=endDate)
    if country:
        filters &= Q(Country=country)

    fields = ['Country','Exporter','Importer','ShipDate','Quantity','Price','Currency','HSCode','Description']
    exportData = models.ExportData.objects.filter(filters).values(*fields)
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)

    dfExportData['Price'] = dfExportData['Price'].astype(float)

    dfExportData['Country'] = dfExportData['Country'].apply(convertCountryCodeToName)

    return dfExportData

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

def GetExportDataTable(startDate, endDate, country):
    dfExportData = getExportData(startDate, endDate, country)

    dfExportData['Value'] = dfExportData['Quantity'] * dfExportData['Price']

    return dfToListOfDicts(dfExportData)