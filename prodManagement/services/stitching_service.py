import pandas as pd
from typing import Dict, List, Tuple, Any

from django.db.models import Q, F
from django.forms.models import model_to_dict

from .. import models
from core.services.generic_services import dfToListOfDicts, convertTexttoObject, updateModelWithDF
from core.services import generic_services
from core.constants import prod

def GetOperationsList():
    fields = ['id', 'Name', 'Section', 'Category', 'SkillLevel', 'SMV', 'MachineType', 'Rate']
    operations = models.Operation.objects.all().values(*fields)
    dfOperations = pd.DataFrame(operations) if operations else pd.DataFrame(columns=fields)
    del operations

    mappingDict = {item['value']: item['text'] for item in prod.operationSections}
    dfOperations['Section'] = dfOperations['Section'].map(mappingDict)

    mappingDict = {item['value']: item['text'] for item in prod.machineTypes}
    dfOperations['MachineType'] = dfOperations['MachineType'].map(mappingDict)

    dfOperations['RatePerSAM'] = (dfOperations['Rate'] / dfOperations['SMV']).mask(dfOperations['SMV'] == 0, 0).round(2)

    return dfToListOfDicts(dfOperations)

#TODO: This would be obsolete once we shift to next
def GetOperations(sectionFilter: str, machineType: str, skillLevel: str, ratePerSAM: str):
    operations = models.Operation.objects

    filters = Q()
    if sectionFilter:
        filters &= Q(Section=sectionFilter)
    if machineType:
        filters &= Q(MachineType=machineType)
    if skillLevel:
        filters&= Q(SkillLevel=skillLevel)
    
    fields = ['id', 'Name', 'Section', 'Category', 'SkillLevel', 'SMV', 'MachineType', 'Rate']
    if filters:
        operations = operations.filter(filters).values(*fields)
    else:
        operations = operations.all().values(*fields)
    del sectionFilter, machineType, filters

    if operations:
        dfOperations = pd.DataFrame(operations)
    else:
        dfOperations = pd.DataFrame(columns=fields)
    del operations, fields
    
    sections = prod.operationSections
    sectionMapping = {item['value']: item['text'] for item in sections if item['value'] is not None}
    dfOperations['Section'] = dfOperations['Section'].map(sectionMapping).fillna(dfOperations['Section'])
    del sections, sectionMapping

    machineTypes = prod.machineTypes
    machineTypeMapping = {item['value']: item['text'] for item in machineTypes if item['value'] is not None}
    dfOperations['MachineType'] = dfOperations['MachineType'].map(machineTypeMapping).fillna(dfOperations['MachineType'])
    del machineTypes, machineTypeMapping

    if ratePerSAM:
        dfOperations['RatePerSAM'] = dfOperations['Rate'] / dfOperations['SMV']
        ratePerSAM = float(ratePerSAM)
        dfOperations = dfOperations[dfOperations['RatePerSAM'] >= ratePerSAM]
        dfOperations.drop(inplace=True, columns=['RatePerSAM'])

    return generic_services.dfToListOfDicts(dfOperations)

def AddOperationAPI(data: Dict[str, Any]):
    data['Name'] = data.pop('OperationName')
    data['SkillLevel'] = data.pop('Level')
    data['SMV'] = data.pop('SAM')
    data['Code'] = data.pop('OperationCode')

    operation = models.Operation(**data)  
    operation.MachineRequirement = (operation['MachineType'] != 'Manu')

    operation.save()

    return operation.id

#TODO: This would be obsolete once we shift to next
def AddOperation (data: Dict):
    #Rename the data keys to match model fields
    data['SkillLevel'] = data.pop('Level')
    data['MachineType'] = data.pop('Type')
    
    try:
        operation = models.Operation(**data)
        operation.save()

        return operation.id
    except Exception as e:
        raise ValueError(e)

def GetDataForOperationUpdate(operation: models.Operation):
    data = model_to_dict(operation)
    return data

#TODO: This would be obsolete once we shift to next
def GetDataForOperation(operation: models.Operation):
    data = model_to_dict(operation)

    return data

def EditOperationAPI(data: Dict[str, Any], operation: models.Operation):
    data['Name'] = data.pop('OperationName')
    data['SkillLevel'] = data.pop('Level')
    data['SMV'] = data.pop('SAM')
    data['Code'] = data.pop('OperationCode')

    for key, value in data.items():
        setattr(operation, key, value)
    
    operation.save()

#TODO: This would be obsolete once we shift to next
def EditOperation (data: Dict, operation: models.Operation):
    #Rename the data keys to match model fields
    data['SkillLevel'] = data.pop('Level')
    data['MachineType'] = data.pop('Type')

    try:
        for key, value in data.items():
            setattr(operation, key, value) 
        operation.save()
    except Exception as e:
        raise ValueError(e)

def GetOperationsForRateApproval():
    filters = Q(approvedrates__isnull=True) | ~Q(approvedrates__Rate=F('Rate'))
    fields = ['id', 'Name', 'Section', 'SkillLevel', 'SMV', 'Rate']
    operations = models.Operation.objects.filter(filters).values(*fields)
    dfOperations = pd.DataFrame(operations) if operations else pd.DataFrame(columns=fields)
    del operations, filters

    fields = ['id', 'Operation', 'Rate']
    approvedRates = models.ApprovedRates.objects.filter(Operation__in=dfOperations['id'].unique().tolist()).values(*fields)
    dfApprovedRates = pd.DataFrame(approvedRates) if approvedRates else pd.DataFrame(columns=fields)
    del approvedRates, fields

    dfApprovedRates.rename(inplace=True, columns={'id': 'ApprovedRateId', 'Operation': 'id', 'Rate': 'ApprovedRate'})

    dfOperations = pd.merge(left=dfOperations, right=dfApprovedRates, on='id', how='left')
    del dfApprovedRates

    mappingDict = {item['value']: item['text'] for item in prod.operationSections}
    dfOperations['Section'] = dfOperations['Section'].map(mappingDict)

    return dfToListOfDicts(dfOperations)

def ApproveRates(data: Dict[str, List[Dict[str, int]]], approvedBy: models.User):
    rates = data['Operations']
    dfRates = pd.DataFrame(rates)

    if dfRates.empty:
        return
    
    dfRates.rename(inplace=True, columns={'id': 'Operation', 'PreviousId': 'id'})

    dfRates['ApprovedBy'] = approvedBy
    dfRates['Operation'] = convertTexttoObject(models.Operation, dfRates['Operation'], 'id')

    updateModelWithDF(models.ApprovedRates, dfRates, dfRates[['id']])

def GetMachineList():
    fields = ['id', 'MachineId', 'Type', 'FunctionStatus', 'Manufacturer', 'ModelNumber', 'SerialNumber', 'Department']
    machines = models.Machine.objects.all().values(*fields)
    dfMachines = pd.DataFrame(machines) if machines else pd.DataFrame(columns=fields)
    del machines

    mappingDict = {item['value']: item['text'] for item in prod.machineTypes}
    dfMachines['Type'] = dfMachines['Type'].map(mappingDict)
    
    return dfToListOfDicts(dfMachines)

#TODO: This would be obsolete when we shift to next
def GetMachines(
        type: str,
        status: str,
        manufacturer: str,
        department: str
)-> Tuple[List[Dict[str, any]], List[str], List[str], List[str]]:
    fields = ['id', 'MachineId', 'Type', 'FunctionStatus', 'Manufacturer', 'ModelNumber', 'SerialNumber', 'Department']
    
    filters = Q()
    if type:
        filters &= Q(Type=type)
    if status:
        filters &= Q(FunctionStatus=status)
    if manufacturer:
        filters &= Q(Manufacturer=manufacturer)
    if department:
        filters &= Q(Department=department)
    
    if filters:
        machines = models.Machine.objects.filter(filters).values(*fields)
    else:
        machines = models.Machine.objects.all().values(*fields)
    
    if machines:
        dfMachines = pd.DataFrame(machines)
    else:
        dfMachines = pd.DataFrame(columns=fields)
    del machines, fields, filters

    dfMachineTypes = pd.DataFrame(prod.machineTypes)

    dfMachines = pd.merge(left=dfMachines, right=dfMachineTypes, left_on='Type', right_on='value', how='left')
    del dfMachineTypes
    dfMachines.drop(inplace=True, columns=['Type', 'value'])
    dfMachines.rename(inplace=True, columns={'text': 'Type'})

    machines = generic_services.dfToListOfDicts(dfMachines)

    return machines

def AddMachineAPI(data: Dict[str, any]):
    conflictExists = models.Machine.objects.filter(
        Q(MachineId=data.get('MachineId')) | 
        Q(SerialNumber=data.get('SerialNumber'))
    ).exists()
    if conflictExists:
        raise ValueError('Duplicate Data provided')

    data['Type'] = data.pop('MachineType')

    if data.get('Department'):
        data['Department'] = models.Department.objects.get(Name=data['Department'])
    
    machine = models.Machine(**data)
    machine.save()

    return machine.id

#TODO: This would be obsolete once we shift to next
def AddMachine(data: Dict):
    data = {key: None if value == 'null' else value for key, value in data.items()}
    
    #Convert department from string to department object if it is provided
    if data['Department']:
        data['Department'] = models.Department.objects.get(Name=data['Department'])

    try:
        machine = models.Machines(**data)
        machine.save()

        return machine.id
    except Exception as e:
        raise ValueError(e)

def GetDataForMachineUpdate(machine: models.Machine):
    return model_to_dict(machine)

#TODO: This woudl be obsolete once we shift to next
def GetDataForMachine (machine: models.Machine):
    data = model_to_dict(machine)
    
    return data

def EditMachineAPI(data: Dict[str, Any], machine: models.Machine):
    conflictExists = models.Machine.objects.filter(
        Q(MachineId=data.get('MachineId')) | 
        Q(SerialNumber=data.get('SerialNumber'))
    ).exclude(id=machine.id).exists()
    if conflictExists:
        raise ValueError('Duplicate Data provided')
    
    data['Type'] = data.pop('MachineType')

    if data.get('Department'):
        data['Department'] = models.Department.objects.get(Name=data['Department'])
    
    for key, value in data.items():
        setattr(machine, key, value)
    
    machine.save()

#TODO: This would be obsolete once we shift to next
def EditMachine (data: Dict, machine: models.Machine):
    data = {key: None if value == 'null' else value for key, value in data.items()}
    
    #Convert department from string to department object if it is provided
    if data['Department']:
        data['Department'] = models.Department.objects.get(Name=data['Department'])

    try:
        for key, value in data.items():
            setattr(machine, key, value)
        machine.save()
    except Exception as e:
        raise ValueError(e)