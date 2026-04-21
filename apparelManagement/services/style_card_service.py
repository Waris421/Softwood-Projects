import pandas as pd
import numpy as np

from typing import List, Dict

from django.forms.models import model_to_dict
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.models import User

from .. import models
from core.services.generic_services import convertTexttoObject, updateModelWithDF, dfToListOfDicts, convertTextToBool
from core.constants.prod import threadCounts

def normalizePreReqs(value):
    if isinstance(value, list):
        return value
    
    if isinstance(value, str):
        return [value]
    
    if pd.isna(value):
        return []
    
    return []

def calculateFinalConsumption(dfConsumption: pd.DataFrame) -> pd.Series:
    inventories = models.Inventory.objects.filter(Code__in=dfConsumption['InventoryCode'].to_list())
    inventories = inventories.values('Code','Unit')
    if inventories:
        dfConsInventories = pd.DataFrame(inventories)
    else:
        dfConsInventories = pd.DataFrame(columns=['Code','Unit'])
    del inventories

    invUnits = models.Unit.objects.filter(Name__in=dfConsInventories['Unit'].to_list())
    invUnits = invUnits.values('Name','Group','Factor')
    if invUnits:
        dfInvUnits = pd.DataFrame(invUnits)
    else:
        dfInvUnits = pd.DataFrame(columns=['Name','Group','Factor'])
    del invUnits

    consUnits = models.Unit.objects.filter(Name__in=dfConsumption['Unit'].to_list())
    consUnits = consUnits.values('Name','Group','Factor')
    if consUnits:
        dfConsUnits = pd.DataFrame(consUnits)
    else:
        dfConsUnits = pd.DataFrame(columns=['Name','Group','Factor'])
    del consUnits

    dfConsumption = pd.merge(left=dfConsumption, right=dfConsUnits, left_on='Unit', right_on='Name', how='left')
    del dfConsUnits
    dfConsumption.drop(inplace=True, columns=['Name'])
    dfConsumption.rename(inplace=True, columns={'Group':'ConsUnitGroup','Factor':'ConsUnitFactor'})

    dfConsInventories = pd.merge(left=dfConsInventories, right=dfInvUnits, left_on='Unit', right_on='Name', how='left')
    del dfInvUnits
    dfConsInventories.drop(inplace=True, columns=['Name'])
    dfConsInventories.rename(inplace=True, columns={'Unit':'InvUnit','Group':'InvUnitGroup','Factor':'InvUnitFactor'})

    dfConsumption = pd.merge(left=dfConsumption, right=dfConsInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfConsInventories
    dfConsumption.drop(inplace=True, columns=['Code'])
    dfConsumption.rename(inplace=True, columns={'Unit_x':'Unit'})

    if (flagColGroupMismatch(dfConsumption[['ConsUnitGroup','InvUnitGroup']])):
        raise ValueError('Incorrect Consumption Unit')
    
    dfConsumption.drop(inplace=True, columns=['ConsUnitGroup','InvUnitGroup','InvUnit'])

    dfConsumption['ConsUnitFactor'] = np.where(dfConsumption['ConsUnitFactor'].isna(), 1/dfConsumption['InvUnitFactor'], dfConsumption['ConsUnitFactor'])

    dfConsumption['Consumption'] = dfConsumption['Consumption'].astype(float)

    dfConsumption['FinalCons'] = dfConsumption['Consumption'] * dfConsumption['InvUnitFactor'] * dfConsumption['ConsUnitFactor']    

    return dfConsumption['FinalCons']

def flagColGroupMismatch(df: pd.DataFrame) -> bool:
    flag = (df['ConsUnitGroup'].notna()) & (df['InvUnitGroup'].notna()) & (df['ConsUnitGroup'] != df['InvUnitGroup'])

    return flag.any()

def GetStyleCards():
    fields = ['StyleCode', 'StyleName', 'Customer', 'Category', 'RoutePreset__Name']
    styles = models.StyleCard.objects.all().values(*fields)
    dfStyles = pd.DataFrame(styles) if styles else pd.DataFrame(columns=fields)
    del styles

    fields = ['Style','InventoryCode__Name']
    fabricsCodes = models.StyleConsumption.objects.filter(Style__in=dfStyles['StyleCode'].to_list()).filter(Type='Fab').values(*fields)
    dfFabricCodes = pd.DataFrame(fabricsCodes) if fabricsCodes else pd.DataFrame(columns=fields)
    del fabricsCodes

    #Remove the style card of sampling
    dfStyles = dfStyles[dfStyles['StyleCode'] != 'GEN-Sampling']

    dfStyles.rename(inplace=True, columns={'StyleCode': 'Code', 'StyleName': 'Name', 'RoutePreset__Name': 'Route'})
    dfFabricCodes.rename(inplace=True, columns={'Style': 'Code', 'InventoryCode__Name': 'Fabric'})
    
    #Take only first fabric code as that is normally the main fabric
    dfFabricCodes = dfFabricCodes.drop_duplicates(subset=['Code'], keep='first')

    dfStyles = pd.merge(left=dfStyles, right=dfFabricCodes, on='Code', how='left')
    
    return dfToListOfDicts(dfStyles)

#TODO: This would be obsolete when we shift to next
def getStyleCard (customer:str):
    filters = Q()
    if customer:
        filters &= Q(Customer=customer)
    fields = ['StyleCode','Customer','Category']
    styles = models.StyleCard.objects.filter(filters).values(*fields)
    dfStyles = pd.DataFrame(styles) if styles else pd.DataFrame(columns=fields)
    del styles

    fields = ['Style','InventoryCode']
    fabricsCodes = models.StyleConsumption.objects.filter(Style__in=dfStyles['StyleCode'].to_list()).filter(Type='Fab').values(*fields)
    dfFabricCodes = pd.DataFrame(fabricsCodes) if fabricsCodes else pd.DataFrame(columns=fields)
    del fabricsCodes

    fields = ['Code', 'Name']
    fabrics = models.Inventory.objects.filter(Code__in=dfFabricCodes['InventoryCode'].to_list()).values(*fields)
    dfFabrics = pd.DataFrame(fabrics) if fabrics else pd.DataFrame(columns=fields)
    
    dfFabrics = pd.merge(left=dfFabricCodes, right=dfFabrics, left_on='InventoryCode', right_on='Code', how='right')
    del dfFabricCodes
    dfFabrics.drop(inplace=True, columns=['InventoryCode','Code'])

    dfStyles = pd.merge(left=dfStyles, right=dfFabrics, left_on='StyleCode', right_on='Style', how='left')
    del dfFabrics
    dfStyles.drop(inplace=True, columns=['Style'])
    dfStyles.rename(inplace=True, columns={'Name':'FabricName'})

    dfStyles = dfStyles.groupby('StyleCode').agg(
        Customer=('Customer', 'first'),
        Category=('Category', 'first'),
        Fabric=('FabricName', 'first')
        ).reset_index().sort_values(by=['Customer', 'StyleCode'])

    return dfToListOfDicts(dfStyles)

def GetRoutePresetStages(routePreset: models.RoutePreset):
    fields = ['id', 'Stage', 'PreReqs__Stage']
    stages = models.RoutePresetStage.objects.filter(RoutePreset=routePreset).values(*fields)
    dfStages = pd.DataFrame(stages) if stages else pd.DataFrame(columns=fields)
    del stages

    dfStages.rename(inplace=True, columns={'PreReqs__Stage':'PreReqs'})
    dfStages = dfStages.groupby(['id', 'Stage']).agg(
        PreReqs=('PreReqs', lambda x: list(x.dropna()))
    ).reset_index()
    dfStages.drop(inplace=True, columns=['id'])
    
    return dfToListOfDicts(dfStages)

def AddStyleCard(
        dfStyle: pd.DataFrame,
        dfVariants: pd.DataFrame,
        dfRoute: pd.DataFrame,
        ) -> str:
    '''Save a new style Card'''
    #Get the style code
    styleCode = dfStyle['StyleCode'][0]
    #Return error is style code is blank
    if(styleCode == ''):
        raise ValueError ('No Style Code is Provided')
    
    if '/' in styleCode:
        raise ValueError('No Slashes are allowed in Style Code')

    try:
        presetId = int(dfRoute['RoutePreset'].iloc[0])
        routePreset = models.RoutePreset.objects.get(id=presetId) 
    except:
        raise ValueError('Invalid Route Selected')

    #Replace any blank variants with Nan
    dfVariants = dfVariants.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    dfVariants['Variant1'] = np.where(dfVariants['Variant1'].str.len()==0,np.nan, dfVariants['Variant1'])
    dfVariants['Variant2'] = np.where(dfVariants['Variant2'].str.len()==0,np.nan, dfVariants['Variant2'])
    dfVariants = dfVariants[~dfVariants.isnull().all(axis=1)]

    #Raise error if no variants are provided
    if dfVariants.empty:
        raise ValueError('No Variant is provided')

    if dfRoute.empty:
        raise ValueError('No Production route is provided')

    #Convert Customer to model objects and assign to style
    dfStyle['Customer'] = convertTexttoObject(models.Customer, dfStyle['Customer'],'Name')
    
    styleCard = dfStyle.iloc[0].to_dict()
    styleCard['RoutePreset'] = routePreset
    
    try:
        #Try to fetch style and if found, raise error
        models.StyleCard.objects.get(StyleCode=styleCard['StyleCode'])    
        raise ValueError(f"StyleCard with StyleCode: {styleCard['StyleCode']}, already exists.")
    except models.StyleCard.DoesNotExist:
        #Create a new style Card if it is not found already
        styleCard = models.StyleCard(**styleCard)
        styleCard.save()
    except Exception as e:
        #Raise any other error, if found to be safe.
        raise LookupError(f"Error saving style card: {e}") 

    #Create a Variant1 DF from main DF and remove blanks
    dfVariants1 = dfVariants['Variant1'].dropna().to_frame()

    #Create a Variant2 DF from main DF and remove blanks
    dfVariants2 = dfVariants['Variant2'].dropna().to_frame()

    #Cross Join Varian1 and Variant2 DFs.
    dfVariants = pd.merge(left=dfVariants1, right=dfVariants2, how="cross")
    #If dfVariants is still empty, it means that there is only one column of variants. Set it to which one is non-empty
    if dfVariants.empty:
        dfVariants = dfVariants2 if dfVariants1.empty else dfVariants1
    del dfVariants1, dfVariants2

    dfVariants['Style'] = styleCard

    dfVariants['VariantCode'] = dfVariants['Variant1']+'-'+dfVariants['Variant2']
    dfVariants.drop(inplace=True, columns=['Variant1','Variant2'])

    
    for _, row in dfVariants.iterrows():
        newEntry = models.StyleVariant(**row.to_dict())
        newEntry.save()

    return styleCard.StyleCode

def UpdateStyleCard(
        dfStyle: pd.DataFrame,
        dfVariants: pd.DataFrame,
        dfConsumption: pd.DataFrame,
        dfRoute: pd.DataFrame,
        dfAttachments: pd.DataFrame,
        ) -> None:
    '''Edit the style card based on the updated data'''
    dfAttachments = dfAttachments[dfAttachments['File'] != 'undefined']
    
    #Return error is style code is blank
    if(dfStyle['StyleCode'][0] == ''):
        raise ValueError ('No Style Code is Provided')
    
    try:
        presetId = int(dfRoute['RoutePreset'].iloc[0])
        routePreset = models.RoutePreset.objects.get(id=presetId) 
    except:
        raise ValueError('Invalid Route Selected')
    
    dfStyle['Customer'] = convertTexttoObject(models.Customer, dfStyle['Customer'], 'Name')
    
    #Create dict from the provided data, to be able to save in database
    styleCard = dfStyle.iloc[0].to_dict()
    del dfStyle
    
    styleCard['RoutePreset'] = routePreset
    styleCard = models.StyleCard(**styleCard)
    styleCard.save()

    fields = ['id','VariantCode']
    previousVariants = models.StyleVariant.objects.filter(Style=styleCard).values(*fields)
    if previousVariants:
        dfPreviousVariants = pd.DataFrame(previousVariants)
    else:
        dfPreviousVariants = pd.DataFrame(columns=fields)
    del previousVariants

    fields = ['id']
    previousConsumption = models.StyleConsumption.objects.filter(Style=styleCard).values(*fields)
    if previousConsumption:
        dfPreviousConsumption = pd.DataFrame(previousConsumption)
    else:
        dfPreviousConsumption = pd.DataFrame(columns=fields)
    del previousConsumption

    fields = ['id']
    previousAttachments = styleCard.Attachments.all().values(*fields)
    dfPreviousAttachments = pd.DataFrame(previousAttachments) if previousAttachments else pd.DataFrame(columns=fields)
    del previousAttachments
    
    dfVariants.rename(inplace=True, columns={'Variant':'VariantCode'})
    dfVariants = pd.merge(left=dfVariants, right=dfPreviousVariants, left_on='VariantCode', right_on='VariantCode', how='left')

    dfVariants['Style'] = styleCard
    try:
        updateModelWithDF(models.StyleVariant, dfVariants, dfPreviousVariants)
    except Exception as e:
        raise ValueError(f'Error Saving Variants: {e}')
    del dfVariants, dfPreviousVariants

    dfConsumption = dfConsumption[dfConsumption['InvCode'].str.len() > 0]

    dfConsumption['id'] = np.where(dfConsumption['id']=='None', None, dfConsumption['id'])
    dfConsumption['id'] = np.where(dfConsumption['id'].str.len()==0, None, dfConsumption['id'])
    
    dfConsumption.rename(inplace=True, columns={'InvCode':'InventoryCode', 'type': 'Type'})
    
    dfConsumption['Style'] = styleCard

    dfConsumption['Consumption'] = np.where(dfConsumption['Consumption'].str.len()==0, 0, dfConsumption['Consumption'])
    
    dfConsumption['FinalCons'] = calculateFinalConsumption(dfConsumption[['InventoryCode','Unit','Consumption']])

    dfConsumption['InventoryCode'] = convertTexttoObject(models.Inventory, dfConsumption['InventoryCode'], 'Code')

    dfConsumption['Unit'] = convertTexttoObject(models.Unit, dfConsumption['Unit'], 'Name')

    dfConsumption['HasVariant'] = np.where(dfConsumption['HasVariant'] == 'true', True, False)
    
    dfConsumption['SizeDetails'] = np.where(dfConsumption['SizeDetails']=='None', '', dfConsumption['SizeDetails'])

    dfPreviousConsumption['id'] = dfPreviousConsumption['id'].astype(str)

    dfDeletedConsumption = dfPreviousConsumption[~dfPreviousConsumption['id'].isin(dfConsumption['id'])]
    for _, row in dfDeletedConsumption.iterrows():
        models.StyleConsumption.objects.get(id=row['id']).delete()
    
    del dfPreviousConsumption, dfDeletedConsumption

    for _, row in dfConsumption.iterrows():
        if row['id']:
            consumption = models.StyleConsumption.objects.get(id=row['id'])
            for key, value in row.to_dict().items():
                if key != 'id':
                    setattr(consumption, key, value)
        else:
            consumption = models.StyleConsumption(**row)
        consumption.save()
    
    dfAttachments['Content'] = styleCard
    for _, row in dfAttachments.iterrows():
        if row['id']:
            rowDict = row.to_dict()
            attachment = models.Attachment.objects.get(id=rowDict.pop('id'))

            for key, value in rowDict.items():
                setattr(attachment, key, value)
        else:
            row['id'] = None
            attachment = models.Attachment(**row)
        
        attachment.save()
 
def ProcessStyleData(styleCard: models.StyleCard):   
    variants = models.StyleVariant.objects.filter(Style=styleCard).values('VariantCode')
    
    fields = ['id','InventoryCode','Consumption','Unit','Type','FinalCons','HasVariant','SizeDetails']
    consumption = models.StyleConsumption.objects.filter(Style=styleCard).values(*fields)
    if consumption:
        dfConsumption = pd.DataFrame(consumption)
    else:
        dfConsumption = pd.DataFrame(columns = fields)
    del consumption
    
    fields = ['Code','Name']
    inventories = models.Inventory.objects.filter(Code__in=dfConsumption['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields

    styleAttachments = styleCard.Attachments.all()
    
    dfConsumption = pd.merge(left=dfConsumption, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfConsumption.drop(inplace=True, columns=['Code'])
    dfConsumption.rename(inplace=True, columns={'Name':'InventoryName'})

    dfConsumption['InventoryName'] = dfConsumption['InventoryName'].astype(str)+' - '+dfConsumption['InventoryCode'].astype(str)

    cols = [i for i in dfConsumption]
    consumption = [dict(zip(cols, i)) for i in dfConsumption.values]
    del dfConsumption

    if not consumption:
        consumption = [model_to_dict(models.StyleConsumption())]

    fields = ['id', 'Stage', 'PreReqs__Stage']
    route = models.StyleRoute.objects.filter(Style=styleCard).values(*fields)
    
    if route:
        dfRoute = pd.DataFrame(route)
    else:
        emptyRow = {'id':[''], 'Stage':[''], 'PreReqs__Stage':['']}
        dfRoute = pd.DataFrame(emptyRow)
    del route, fields
    
    dfRoute.rename(inplace=True, columns={'PreReqs__Stage':'PreReqs'})
    dfRoute = dfRoute.groupby(['id', 'Stage']).agg(
        PreReqs=('PreReqs', lambda x: list(x.dropna()))
    ).reset_index()

    serializedAttachments = []
    for attachment in styleAttachments:
        serializedAttachments.append({
            'id': attachment.id,
            'FileUrl': attachment.File.url,
            'FileName': attachment.File.name.split('/')[-1],
            'Description': attachment.Description,
        })
    if not serializedAttachments:
        serializedAttachments.append({
            'id': '',
            'FileUrl': '',
            'FileName': '',
            'Description': '',
        })
    
    return model_to_dict(styleCard), variants, consumption, dfToListOfDicts(dfRoute), serializedAttachments

def GetThreadConsRequests(statusStr:str):
    isClosed = convertTextToBool(statusStr)

    fields = ['id','RequestDate', 'RequestBy', 'IsClosed']
    requests = models.ThreadConsumptionRequest.objects.filter(IsClosed=isClosed).values(*fields)
    dfRequests = pd.DataFrame(requests) if requests else pd.DataFrame(columns=fields)
    del requests

    fields = ['id', 'first_name', 'last_name']
    users = User.objects.filter(id__in=dfRequests['RequestBy'].to_list()).values(*fields)
    dfUsers = pd.DataFrame(users) if users else pd.DataFrame(columns=fields)
    del users

    fields = ['Request', 'Style']
    styles = models.ThreadConsumptionRequestStyles.objects.filter(Request__in=dfRequests['id'].to_list()).values(*fields)
    dfStyles = pd.DataFrame(styles) if styles else pd.DataFrame(columns=fields)
    del styles

    dfUsers['FullName'] = dfUsers['first_name']+' '+dfUsers['last_name']
    dfUsers.drop(inplace=True, columns=['first_name', 'last_name'])

    dfRequests.rename(inplace=True, columns={'id': 'RequestNumber'})

    dfRequests = pd.merge(left=dfRequests, right=dfUsers, left_on='RequestBy', right_on='id', how='left')
    del dfUsers
    dfRequests.drop(inplace=True, columns=['id', 'RequestBy'])
    
    dfRequests = pd.merge(left=dfRequests, right=dfStyles, left_on='RequestNumber', right_on='Request', how='left')
    del dfStyles
    dfRequests.drop(inplace=True, columns=['Request'])

    dfRequests = dfRequests.groupby('RequestNumber').agg({
        'RequestDate': 'first',
        'IsClosed': 'first',
        'FullName': 'first',
        'Style': lambda x: ', '.join(x.astype(str))
    }).reset_index()

    dfRequests['Status'] = dfRequests['IsClosed'].map({True: 'Closed', False: 'Pending'})
    dfRequests.drop(inplace=True, columns=['IsClosed'])
    
    return dfToListOfDicts(dfRequests)

def AddRequestForThreadCons(dfRequest: pd.DataFrame, user: User):   
    dfRequest['Style'] = dfRequest['Style'].str.strip().replace('', np.nan).dropna()
    dfRequest['Style'] = convertTexttoObject(models.StyleCard, dfRequest['Style'], 'StyleCode')

    dfRequest['Thread'] = dfRequest['Thread'].str.strip().replace('', np.nan).dropna()
    
    stylesList = dfRequest['Style'].dropna().to_list()
    threadList = dfRequest['Thread'].dropna().to_list()
   
    if not stylesList:
        raise ValueError('No Styles Provided')
    if not threadList:
        raise ValueError('No Threads Provided')

    with transaction.atomic():
        request = models.ThreadConsumptionRequest(RequestBy=user)
        request.save()

        styleEntries = [
            models.ThreadConsumptionRequestStyles(Style=style, Request=request)
            for style in stylesList
        ]
        models.ThreadConsumptionRequestStyles.objects.bulk_create(styleEntries)
        
        
        threadEntries = [
            models.ThreadConsumptionRequestThreads(Thread=thread, Request=request)
            for thread in threadList
        ]
        models.ThreadConsumptionRequestThreads.objects.bulk_create(threadEntries)

    return request.id

def ProcessConsRequestData(request: models.ThreadConsumptionRequest):
    fields = ['id', 'Style']
    styles = models.ThreadConsumptionRequestStyles.objects.filter(Request=request).values(*fields)
    dfStyles = pd.DataFrame(styles) if styles else pd.DataFrame(columns=fields)

    fields = ['id', 'Thread']
    threads = models.ThreadConsumptionRequestThreads.objects.filter(Request=request).values(*fields)
    dfThreads = pd.DataFrame(threads) if threads else pd.DataFrame(columns=fields)

    dfStyles.rename(inplace=True, columns={'id': 'StyleId'})
    dfThreads.rename(inplace=True, columns={'id': 'ThreadId'})

    dfCombined = pd.concat([dfStyles, dfThreads], axis=1).fillna('')

    return dfToListOfDicts(dfCombined)

def UpdateRequestForThreadCons(request: models.ThreadConsumptionRequest, dfRequest: pd.DataFrame):
    dfStyles = dfRequest[['StyleId', 'Style']].replace('', np.nan).dropna(how='all')
    dfThreads = dfRequest[['ThreadId', 'Thread']].replace('', np.nan).dropna(how='all')
    del dfRequest

    fields = ['id']
    previousStyles = models.ThreadConsumptionRequestStyles.objects.filter(Request=request).values(*fields)
    dfPreviousStyles = pd.DataFrame(previousStyles) if previousStyles else pd.DataFrame(columns=fields)
    del previousStyles

    fields = ['id']
    previousThreads = models.ThreadConsumptionRequestThreads.objects.filter(Request=request).values(*fields)
    dfPreviousThreads = pd.DataFrame(previousThreads) if previousThreads else pd.DataFrame(columns=fields)
    del previousThreads
    
    dfStyles.rename(inplace=True, columns={'StyleId': 'id'})
    dfStyles['Style'] = convertTexttoObject(models.StyleCard, dfStyles['Style'], 'StyleCode')
    dfStyles['Request'] = request

    try:
        updateModelWithDF(models.ThreadConsumptionRequestStyles, dfStyles, dfPreviousStyles)
    except Exception as e:
        raise ValueError(f'Error saving Styles: {e}')
    
    dfThreads.rename(inplace=True, columns={'ThreadId': 'id'})
    dfThreads['Request'] = request

    try:
        updateModelWithDF(models.ThreadConsumptionRequestThreads, dfThreads, dfPreviousThreads)
    except Exception as e:
        raise ValueError(f'Error saving Styles: {e}')
    
    request.IsClosed = False
    request.save()

def ProcessThreadConsumptionData(request: models.ThreadConsumptionRequest):
    fields = ['id', 'Thread']
    threads = models.ThreadConsumptionRequestThreads.objects.filter(Request=request).values(*fields)
    
    fields = ['Style']
    styles = models.ThreadConsumptionRequestStyles.objects.filter(Request=request).values(*fields)

    try:
        consumption = models.ThreadConsumption.objects.get(Request=request)
        
        fields = ['id', 'Operation', 'Frequency', 'StitchType', 'Factor', 'ThreadType', 'NeedleCount', 'LooperCount','ConsumptionValue']
        consumptionThreads = models.ThreadConsumptionThreads.objects.filter(Consumption=consumption).values(*fields)
        dfConsumptionThreads = pd.DataFrame(consumptionThreads) if consumptionThreads else pd.DataFrame(columns=fields)
        del consumptionThreads

        dfConsumptionThreads.rename(inplace=True, columns={'ConsumptionValue':'Consumption'})
        addedData = dfToListOfDicts(dfConsumptionThreads)
        del dfConsumptionThreads
    except models.ThreadConsumption.DoesNotExist:
        addedData = []
    except Exception as e:
        raise LookupError(e)

    return model_to_dict(request), threads, addedData, styles

def SaveThreadConsumption(request: models.ThreadConsumptionRequest, data: List[Dict[str, str|int|float]], isFinal: bool):
    dfData = pd.DataFrame(data)
    if dfData.empty:
        raise ValueError('No Data Provided')
    
    print(data)
    try:
        consumption = models.ThreadConsumption.objects.get(Request=request)
    except models.ThreadConsumption.DoesNotExist:
        consumption = models.ThreadConsumption(Request=request)
        consumption.save()
    except Exception as e:
        raise LookupError(e)

    fields = ['id']
    previousConsThreads = models.ThreadConsumptionThreads.objects.filter(Consumption=consumption).values(*fields)
    dfPreviousConsThreads = pd.DataFrame(previousConsThreads) if previousConsThreads else pd.DataFrame(columns=fields)
    del previousConsThreads
    
    dfData['ThreadType'] = convertTexttoObject(models.ThreadConsumptionRequestThreads, dfData['ThreadType'], 'id')
    
    dfData.rename(inplace=True, columns={'Consumption':'ConsumptionValue'})
    dfData['Consumption'] = consumption

    try:
        updateModelWithDF(models.ThreadConsumptionThreads, dfData, dfPreviousConsThreads)
    except Exception as e:
        raise ValueError(e)

    if isFinal:
        request.IsClosed = True
        request.save()

def ProcessThreadConDataForConversion(request: models.ThreadConsumptionRequest):
    try:
        consumption = models.ThreadConsumption.objects.get(Request=request)
    except:
        raise LookupError('Cannot find consumption for this request')

    fields = ['id', 'Style']
    requestStyles = models.ThreadConsumptionRequestStyles.objects.filter(Request=request).filter(IsConverted=False).values(*fields)
    dfRequestStyles = pd.DataFrame(requestStyles) if requestStyles else pd.DataFrame(columns=fields)
    del requestStyles

    fields = ['id', 'Thread']
    requestThreads = models.ThreadConsumptionRequestThreads.objects.filter(Request=request).values(*fields)
    dfRequestThreads = pd.DataFrame(requestThreads) if requestThreads else pd.DataFrame(columns=fields)
    del requestThreads

    fields = ['Frequency', 'Factor', 'ThreadType', 'NeedleCount', 'LooperCount', 'ConsumptionValue']
    consumptionThreads = models.ThreadConsumptionThreads.objects.filter(Consumption=consumption).values(*fields)
    dfConsumptionThreads = pd.DataFrame(consumptionThreads) if consumptionThreads else pd.DataFrame(columns=fields)
    del consumptionThreads
    
    fields = ['Style', 'InventoryCode', 'InventoryCode__Name']
    styleCardThreads = models.StyleConsumption.objects.filter(Style__in=dfRequestStyles['Style'].to_list()).filter(InventoryCode__Code__startswith='THR').values(*fields)
    dfStyleCardThreads = pd.DataFrame(styleCardThreads) if styleCardThreads else pd.DataFrame(columns=fields)
    del styleCardThreads

    dfConsumptionThreads.rename(inplace=True, columns={'ConsumptionValue': 'Length'})
    
    dfConsumptionThreads = dfConsumptionThreads.melt(
        id_vars=['Frequency', 'Factor', 'ThreadType', 'Length'],
        value_vars=['NeedleCount', 'LooperCount'],
        var_name='Count_Type',
        value_name='Count'
    )
    
    dfConsumptionThreads['Count'] = dfConsumptionThreads['Count'].replace('', np.nan)

    dfConsumptionThreads = dfConsumptionThreads.dropna(subset=['Count']).drop(columns=['Count_Type'])
    
    dfConsumptionThreads['Consumption'] = dfConsumptionThreads['Frequency'] * dfConsumptionThreads['Factor'] * dfConsumptionThreads['Length'] / 100
    dfConsumptionThreads = dfConsumptionThreads.groupby(['ThreadType', 'Count'])['Consumption'].sum().reset_index()

    dfConsumptionThreads = pd.merge(left=dfConsumptionThreads, right=dfRequestThreads, left_on='ThreadType', right_on='id', how='left')
    del dfRequestThreads
    dfConsumptionThreads.drop(inplace=True, columns=['ThreadType'])

    countMapping = {item['value']: item['text'] for item in threadCounts}
    
    dfConsumptionThreads['Count'] = dfConsumptionThreads['Count'].map(countMapping).fillna(dfConsumptionThreads['Count'])

    dfRequestStyles.rename(inplace=True, columns={'id':'value', 'Style':'text'})

    dfStyleCardThreads.rename(inplace=True, columns={'InventoryCode__Name':'InventoryName'})
    dfStyleCardThreads.sort_values(inplace=True, by='InventoryName')

    return dfToListOfDicts(dfRequestStyles), dfToListOfDicts(dfConsumptionThreads), dfToListOfDicts(dfStyleCardThreads)

def ConvertThreadConsumption(requestStyle: models.ThreadConsumptionRequestStyles, dfConsumption: pd.DataFrame):
    if (dfConsumption['InvCode'].str.len()==0).any():
        raise ValueError('Incomplete threads')

    dfConsumption.drop(inplace=True, columns=['Thread', 'Count', 'id'])
    dfConsumption.rename(inplace=True, columns={'InvCode': 'InventoryCode'})

    #Fixed Columns iniiialisation
    dfConsumption['Type'] = 'BW'
    dfConsumption['Unit'] = 'Meter'
    dfConsumption['HasVariant'] = False
    dfConsumption['SizeDetails'] = ''
    dfConsumption['FinalCons'] = calculateFinalConsumption(dfConsumption[['InventoryCode','Unit','Consumption']])

    #Setting columns to objects
    dfConsumption['Style'] = requestStyle.Style
    dfConsumption['InventoryCode'] = convertTexttoObject(models.Inventory, dfConsumption['InventoryCode'], 'Code')
    dfConsumption['Unit'] = convertTexttoObject(models.Unit, dfConsumption['Unit'], 'Name')

    instancesToSave = [models.StyleConsumption(**row) for _, row in dfConsumption.iterrows()]
    
    with transaction.atomic():
        models.StyleConsumption.objects.bulk_create(instancesToSave)
        requestStyle.IsConverted = True
        requestStyle.save()

def GetThreadConsumptions():
    fields = ['id', 'AddedOn', 'Request__id', 'Request__RequestBy__first_name', 'Request__RequestBy__last_name', 'Request__IsClosed']
    consumptions = models.ThreadConsumption.objects.all().values(*fields)
    dfConsumptions = pd.DataFrame(consumptions) if consumptions else pd.DataFrame(columns=fields)
    del consumptions

    fields = ['Request', 'Style']
    consumptionStyles = models.ThreadConsumptionRequestStyles.objects.filter(Request__in=dfConsumptions['Request__id'].to_list()).values(*fields)
    dfConsumptionStyles = pd.DataFrame(consumptionStyles) if consumptionStyles else pd.DataFrame(columns=fields)
    del consumptionStyles

    fields = ['Consumption', 'NeedleCount', 'LooperCount', 'Frequency', 'Factor', 'ConsumptionValue']
    threads = models.ThreadConsumptionThreads.objects.filter(Consumption__in=dfConsumptions['id'].to_list()).values(*fields)
    dfThreads = pd.DataFrame(threads) if threads else pd.DataFrame(columns=fields)
    del threads

    dfConsumptions['RequestBy'] = dfConsumptions['Request__RequestBy__first_name']+' '+dfConsumptions['Request__RequestBy__last_name']
    dfConsumptions.drop(inplace=True, columns=['Request__RequestBy__first_name', 'Request__RequestBy__last_name'])
    dfConsumptions.rename(inplace=True, columns={
        'Request__id':'Request',
        'Request__IsClosed': 'Closed'
    })

    dfConsumptionStyles = dfConsumptionStyles.groupby('Request').agg(
    {
        'Style': lambda x: ', '.join(x.astype(str))
    }).reset_index()

    dfConsumptions = pd.merge(left=dfConsumptions, right=dfConsumptionStyles, on='Request', how='left')
    del dfConsumptionStyles
    dfConsumptions.drop(inplace=True, columns=['Request'])

    #Multiple consumption value by 2 if there are threads in both needle and looper
    hasNeedleThread = (dfThreads['NeedleCount'].str.len() > 0).fillna(False)
    hasLooperThread = (dfThreads['LooperCount'].str.len() > 0).fillna(False)
    combinedMask = hasNeedleThread & hasLooperThread
    dfThreads.loc[combinedMask, 'ConsumptionValue'] = dfThreads.loc[combinedMask, 'ConsumptionValue'] * 2
    del hasNeedleThread, hasLooperThread, combinedMask
    dfThreads.drop(inplace=True, columns=['NeedleCount', 'LooperCount'])
    
    dfThreads['ConsumptionValue'] = dfThreads['Frequency'] * dfThreads['Factor'] * dfThreads['ConsumptionValue'] / 100
    dfThreads.drop(inplace=True, columns=['Frequency', 'Factor'])
    dfThreads = dfThreads.groupby('Consumption').agg(
        {'ConsumptionValue': 'sum'}
    ).reset_index()
    
    dfConsumptions = pd.merge(left=dfConsumptions, right=dfThreads, left_on='id', right_on='Consumption', how='left')
    del dfThreads
    dfConsumptions.drop(inplace=True, columns=['Consumption'])

    dfConsumptions['Status'] = np.where(dfConsumptions['Closed'], 'Closed', 'Pending')
    dfConsumptions.drop(inplace=True, columns=['Closed'])
    
    return dfToListOfDicts(dfConsumptions)