import pandas as pd
import numpy as np

from django.forms.models import model_to_dict
from django.db.models import Q

from .. import models
from core.services.generic_services import convertTexttoObject, updateModelWithDF, dfToListOfDicts

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
    
    dfRoute = dfRoute[dfRoute['Sequence'].str.len() > 0]
    dfRoute = dfRoute[dfRoute['type'].str.len() > 0]

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
    
    if dfRoute['Sequence'].duplicated().any():
        raise ValueError('Incorrect Sequence is Provided')

    #Convert Customer to model objects and assign to style
    dfStyle['Customer'] = convertTexttoObject(models.Customer, dfStyle['Customer'],'Name')
    
    styleCard = dfStyle.iloc[0].to_dict()
    
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

    dfRoute['Style'] = styleCard
    dfRoute['Cost'] = 0.0
    
    dfRoute.rename(inplace=True, columns={'type':'Stage'})

    for _, row in dfRoute.iterrows():
        newEntry = models.StyleRoute(**row.to_dict())
        newEntry.save()

    return styleCard.StyleCode

def UpdateStyleCard(
        dfStyle: pd.DataFrame,
        dfVariants: pd.DataFrame,
        dfConsumption: pd.DataFrame,
        dfRoute: pd.DataFrame,
        ) -> None:
    '''Edit the style card based on the updated data'''
    #Return error is style code is blank
    if(dfStyle['StyleCode'][0] == ''):
        raise ValueError ('No Style Code is Provided')
    dfStyle['Customer'] = convertTexttoObject(models.Customer, dfStyle['Customer'], 'Name')

    #Create dict from the provided data, to be able to save in database
    styleCard = dfStyle.iloc[0].to_dict()
    del dfStyle
    
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

    fields = ['id','Stage']
    previoiusRoute = models.StyleRoute.objects.filter(Style=styleCard).values(*fields)
    if previoiusRoute:
        dfPreviousRoute = pd.DataFrame(previoiusRoute)
    else:
        dfPreviousRoute = pd.DataFrame(columns=fields)
    del previoiusRoute
    
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

    dfRoute.rename(inplace=True, columns={'type':'Stage'})

    dfRoute = dfRoute[dfRoute['Stage'].str.len()>0]
    
    dfRoute['id'] = np.where(dfRoute['id'].str.len()==0, np.nan, dfRoute['id'])
    #This is in response to a bug
    dfRoute['id'] = np.where(dfRoute['id']=='None', np.nan, dfRoute['id'])
    dfRoute['id'] = dfRoute['id'].astype('Int64')

    dfRoute['Style'] = styleCard
    try:
        updateModelWithDF(models.StyleRoute, dfRoute, dfPreviousRoute)
    except Exception as e:
        raise ValueError(f'Error Saving Route: {e}')
 
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

    route = models.StyleRoute.objects.filter(Style=styleCard).values('id', 'Sequence','Stage').order_by('Sequence')
    if not route:
        route = [model_to_dict(models.StyleRoute())]
    
    return model_to_dict(styleCard), variants, consumption, route