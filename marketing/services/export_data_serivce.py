import pandas as pd

from datetime import date, timedelta

from django.db import transaction

from .. import models
from core.services.generic_services import dfToListOfDicts

def getExportData(startDateStr: str, endDateStr: str):
    if startDateStr:
        startDate = date.fromisoformat(startDateStr)
    else:
        today = date.today()
        startDate = date(today.year, today.month, 1)
    
    if endDateStr:
        endDate = date.fromisoformat(endDateStr)
    else:
        today = date.today()
        if today.month == 12:
            firstDayOfNextMonth = date(today.year + 1, 1, 1)
        else:
            firstDayOfNextMonth = date(today.year, today.month + 1, 1)

        endDate = firstDayOfNextMonth - timedelta(days=1)
    
    fields = ['Country','Exporter','Importer','ShipDate','Quantity','Price','Currency','HSCode','Description']
    exportData = models.ExportData.objects.filter(ShipDate__gte=startDate, ShipDate__lte=endDate).values(*fields)
    dfExportData = pd.DataFrame(exportData) if exportData else pd.DataFrame(columns=fields)

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

    dfUploadedData['ShipDate'] = dfUploadedData['ShipDate'].dt.strftime('%Y-%m-%d')

    return dfToListOfDicts(dfUploadedData)
    newEntries = []
    for _, row in dfUploadedData.iterrows():
        newEntry = models.ExportData(**row.to_dict())
        newEntries.append(newEntry)
    #models.ExportData.objects.bulk_create(newEntries)
    print(newEntries)

def GetExportDataTable(startDate, endDate):
    dfExportData = getExportData(startDate, endDate)

    dfExportData['Value'] = dfExportData['Quantity'] * dfExportData['Price']

    return dfToListOfDicts(dfExportData)