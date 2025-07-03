import pandas as pd
import numpy as np

from django.forms.models import model_to_dict

from .. import models
from core.services import generic_services
from core.constants import prod

def calculateSortedContribution(series: pd.Series):
    total = series.sum()
    contribution = (series / total * 100).round(2)
    contribution = dict(sorted(contribution.items(), key=lambda item: item[1], reverse=True))
    return contribution

def AddStyleBulletin(dfBulletin: pd.DataFrame, dfBulletinDetails: pd.DataFrame):
    try:
        styleCard = dfBulletin.iloc[0].to_dict()
        del dfBulletin
        styleCard = styleCard['StyleCard']
        styleCard = models.StyleCard.objects.get(StyleCode=styleCard)  
    except:
        raise LookupError('Style Card Not Found')
    
    try:
        models.StyleBulletin.objects.get(StyleCard=styleCard)
        raise ValueError('Style Bulletin Already Exists')
    except:
        styleBulletin = models.StyleBulletin(StyleCard=styleCard)
        styleBulletin.save()

    dfBulletinDetails = dfBulletinDetails[dfBulletinDetails['Operation'].str.len() > 0]

    dfBulletinDetails['Operation'] = dfBulletinDetails['Operation'].astype(int)
    dfBulletinDetails['Operation'] = generic_services.convertTexttoObject(models.Operation, dfBulletinDetails['Operation'], 'id')
    dfBulletinDetails['StyleBulletin'] = styleBulletin

    dfBulletinDetails['Sequence'] = range(1, len(dfBulletinDetails) + 1)

    dfBulletinDetails = dfBulletinDetails.sort_values(by=['Section', 'Sequence'])

    dfBulletinDetails['IsStart'] = dfBulletinDetails.groupby('Section')['Sequence'].transform(lambda x: x == x.min())
    dfBulletinDetails['IsEnd'] = dfBulletinDetails.groupby('Section')['Sequence'].transform(lambda x: x == x.max())

    for _, row in dfBulletinDetails.iterrows():
        styleBulletinOperation = models.StyleBulletinOperation(**row)
        styleBulletinOperation.save()
    
    return styleBulletin.id

def GetDataForBulletin(styleBulletin: models.StyleBulletin):
    bulletinData = model_to_dict(styleBulletin)
    
    fields = ['id','Operation','Section']
    operations = models.StyleBulletinOperation.objects.filter(StyleBulletin=styleBulletin).order_by('Sequence').values(*fields)
    
    return bulletinData, operations

def UpdateStyleBulletin(styleBulletin: models.StyleBulletin, dfOperations: pd.DataFrame):
    fields = ['id']
    previousOperations = models.StyleBulletinOperation.objects.filter(StyleBulletin=styleBulletin).values(*fields)
    if previousOperations:
        dfPerviousOperations = pd.DataFrame(previousOperations)
    else:
        dfPerviousOperations = pd.DataFrame(columns=fields)
    del previousOperations, fields

    dfOperations = dfOperations[dfOperations['Operation'].str.len() > 0]

    dfOperations['StyleBulletin'] = styleBulletin
    
    dfOperations['Operation'] = dfOperations['Operation'].astype(int)
    dfOperations['Operation'] = generic_services.convertTexttoObject(models.Operation, dfOperations['Operation'], 'id')
    
    dfOperations['Sequence'] = range(1, len(dfOperations) + 1)

    dfOperations = dfOperations.sort_values(by=['Section', 'Sequence'])

    dfOperations['IsStart'] = dfOperations.groupby('Section')['Sequence'].transform(lambda x: x == x.min())
    dfOperations['IsEnd'] = dfOperations.groupby('Section')['Sequence'].transform(lambda x: x == x.max())

    dfOperations['id'] = np.where(dfOperations['id'].str.len() == 0, None, dfOperations['id'])

    generic_services.updateModelWithDF(models.StyleBulletinOperation, dfOperations, dfPerviousOperations)

def GetBulletinList(minSAM: float):
    fields = ['id', 'StyleCard']
    bulletins = models.StyleBulletin.objects.all().values(*fields)
    
    if bulletins:
        dfBulletins = pd.DataFrame(bulletins)
    else:
        dfBulletins = pd.DataFrame(columns=fields)
    del bulletins
    
    fields = ['StyleBulletin', 'Operation', 'Section']
    bulletinOperations = models.StyleBulletinOperation.objects.filter(StyleBulletin__in=dfBulletins['id'].to_list())
    bulletinOperations = bulletinOperations.order_by('StyleBulletin', 'Sequence').values(*fields)

    if bulletinOperations:
        dfBulletinOperations = pd.DataFrame(bulletinOperations)
    else:
        dfBulletinOperations = pd.DataFrame(columns=fields)
    del bulletinOperations

    fields = ['id', 'SkillLevel', 'SMV', 'MachineType', 'Rate']
    operations = models.Operation.objects.filter(id__in=dfBulletinOperations['Operation'].to_list()).values(*fields)

    if operations:
        dfOperations = pd.DataFrame(operations)
    else:
        dfOperations = pd.DataFrame(columns=fields)
    del operations, fields

    dfChangeOverTimes = pd.Series(prod.changeOverTimes).to_frame().reset_index()
    dfChangeOverTimes.rename(inplace=True, columns={'index':'MachineType', 0: 'ChangeOverTime'})

    dfMachineTypes = pd.DataFrame(prod.machineTypes)

    dfSections = pd.DataFrame(prod.operationSections)

    dfOperations = pd.merge(left=dfOperations, right=dfChangeOverTimes, left_on='MachineType', right_on='MachineType', how='left')
    del dfChangeOverTimes

    dfOperations = pd.merge(left=dfOperations, right=dfMachineTypes, left_on='MachineType', right_on='value', how='left')
    del dfMachineTypes

    dfOperations.drop(inplace=True, columns=['MachineType', 'value'])
    dfOperations.rename(inplace=True, columns={'text': 'MachineType'})

    dfBulletinOperations = pd.merge(left=dfBulletinOperations, right=dfOperations, left_on='Operation', right_on='id', how='left')
    del dfOperations
    dfBulletinOperations.drop(inplace=True, columns=['Operation', 'id'])

    dfBulletinOperations = pd.merge(left=dfBulletinOperations, right=dfSections, left_on='Section', right_on='value', how='left')
    del dfSections
    dfBulletinOperations.drop(inplace=True, columns=['Section', 'value'])
    dfBulletinOperations.rename(inplace=True, columns={'text': 'Section'})

    dfBulletinOperations = pd.merge(left=dfBulletinOperations, right=dfBulletins, left_on='StyleBulletin', right_on='id', how='left')
    del dfBulletins
    dfBulletinOperations.drop(inplace=True, columns={'StyleBulletin'})
    dfBulletinOperations.rename(inplace=True, columns={'StyleCard': 'StyleCode'})

    dfBulletinOperations = dfBulletinOperations.groupby(['id', 'StyleCode']).agg(
        SMV=('SMV', 'sum'),
        Rate=('Rate', 'sum'),
        LeadTime = ('ChangeOverTime', 'sum'),
        Sections = ('Section', lambda x: calculateSortedContribution(dfBulletinOperations.loc[x.index, 'SMV'].groupby(dfBulletinOperations.loc[x.index, 'Section']).sum())),
        SkillLevels = ('SkillLevel', lambda x: calculateSortedContribution(dfBulletinOperations.loc[x.index, 'SMV'].groupby(dfBulletinOperations.loc[x.index, 'SkillLevel']).sum())),
        MachineTypes = ('MachineType', lambda x: calculateSortedContribution(dfBulletinOperations.loc[x.index, 'SMV'].groupby(dfBulletinOperations.loc[x.index, 'MachineType']).sum())),
    ).reset_index()

    #Round up the lead-time to the nearest half day.
    dfBulletinOperations['LeadTime'] = np.ceil((dfBulletinOperations['LeadTime']/8) * 2) / 2

    if minSAM:
        dfBulletinOperations = dfBulletinOperations[dfBulletinOperations['SMV']>=minSAM]

    return generic_services.dfToListOfDicts(dfBulletinOperations)

def DuplicateStyleBulletin(sourceBulletin: models.StyleBulletin, targetCode: str):
    if targetCode == '':
        raise ValueError('Please provide a target Code')

    try:
        targetStyle = models.StyleCard.objects.get(StyleCode=targetCode)
    except:
        raise LookupError('Resource not found')
    
    try:
        models.StyleBulletin.objects.get(StyleCard=targetStyle)
        raise ValueError('Style Bulletin Already Exists.')
    except:
        pass
    
    targetBulletin = models.StyleBulletin(StyleCard=targetStyle)
    targetBulletin.save()
    
    targetOperations = models.StyleBulletinOperation.objects.filter(StyleBulletin=sourceBulletin)
    
    for operation in targetOperations:
        operation.id = None
        operation.StyleBulletin = targetBulletin
        operation.save()
    
    return targetBulletin.id

def SummariseBulletin(styleBulletin: models.StyleBulletin, dfCurrentOperations: pd.DataFrame):
    dfCurrentOperations.drop(inplace=True, columns=['Section'])

    fields = ['Operation']
    previousOperations = models.StyleBulletinOperation.objects.filter(StyleBulletin=styleBulletin).values(*fields)

    if previousOperations:
        dfPreviousOperations = pd.DataFrame(previousOperations)
    else:
        dfPreviousOperations = pd.DataFrame(columns=fields)
    del previousOperations

    fields = ['id', 'SMV', 'Rate', 'SkillLevel']
    alloperations = (dfPreviousOperations['Operation'].to_list()) + (dfCurrentOperations['Operation'].astype(int).to_list())
    operations = models.Operation.objects.filter(id__in=alloperations).values(*fields)

    if operations:
        dfOperations = pd.DataFrame(operations)
    else:
        dfOperations = pd.DataFrame(columns=fields)
    del operations, fields

    dfCurrentOperations['Operation'] = dfCurrentOperations['Operation'].astype(int)
    dfBulletinOperations = pd.merge(left=dfCurrentOperations, right=dfPreviousOperations, on='Operation', how='outer', indicator=True)
    del dfCurrentOperations, dfPreviousOperations
    dfBulletinOperations.drop(inplace=True, columns=['id'])

    dfBulletinOperations = pd.merge(left=dfBulletinOperations, right=dfOperations, left_on='Operation', right_on='id', how='left')
    del dfOperations
    dfBulletinOperations.drop(inplace=True, columns={'id'})

    mergeMapping = {'left_only': 'After', 'right_only': 'Before', 'both': 'Both'}
    dfBulletinOperations['_merge'] = dfBulletinOperations['_merge'].replace(mergeMapping)
    del mergeMapping

    summaryData = {}
    for key in ['SMV', 'Rate']:
        summaryData[key] = {'Before': 0, 'After': 0}
    summaryData['SkillLevel'] = {'Before': [], 'After': []}
    
    for _, row in dfBulletinOperations.iterrows():
        merge = row['_merge']
        smv = row['SMV']
        rate = row['Rate']
        skillLevel = int(row['SkillLevel'])

        if merge in ['Before', 'Both']:
            summaryData['SMV']['Before'] += smv
            summaryData['Rate']['Before'] += rate
            summaryData['SkillLevel']['Before'].append(skillLevel)
        
        if merge in ['After', 'Both']:
            summaryData['SMV']['After'] += smv
            summaryData['Rate']['After'] += rate
            summaryData['SkillLevel']['After'].append(skillLevel)

    del dfBulletinOperations

    beforeSkillLevel = summaryData['SkillLevel']['Before']
    if beforeSkillLevel:
        beforeSkillLevel = sum(beforeSkillLevel) / len(beforeSkillLevel)
        summaryData['SkillLevel']['Before'] = round(beforeSkillLevel, 2)
    else:
        summaryData['SkillLevel']['Before'] = 0

    afterSkillLevel = summaryData['SkillLevel']['After']
    if afterSkillLevel:
        afterSkillLevel = sum(afterSkillLevel) / len(afterSkillLevel)
        summaryData['SkillLevel']['After'] = round(afterSkillLevel, 2)
    else:
        summaryData['SkillLevel']['After'] = 0

    return summaryData