import numpy as np
import pandas as pd
import uuid
import re
from dateutil.relativedelta import relativedelta
from typing import Dict, TextIO, BinaryIO
from datetime import datetime

from django.contrib.auth.models import User
from django.forms import model_to_dict
from django.db import transaction
from django.db.models import F
from django.core.cache import cache

from HumanResource import models
from core.services.generic_services import dfToListOfDicts, convertStrToDateTime, convertFullNametoNameParts, convertTexttoObject
from core.constants.generic import EMPLOYEMENT_AGE_IN_YEARS, TODAY

def validateUploader(dfData: pd.DataFrame):
    '''
        Check the employee uploader and show any errors if found
    '''

    dfData['HasError'] = False

    #Define error text
    alreadyExistsSuffix = ' (Already Exists)'
    errorSuffix = ' (Invalid/Not Found)'
    
    #Check for duplicates
    colsToCheck = ['id', 'EmailAddress', 'Username']
    for col in colsToCheck:
        mask = dfData.duplicated(subset=[col], keep=False) & dfData[col].notna()
        dfData.loc[mask, col] = dfData[col].astype(str) + errorSuffix
        dfData.loc[mask, 'HasError'] = True
    
    #Check if employee code already exists
    existingEmployees = set(models.Employee.objects.filter(id__in=dfData['id'].to_list()).values_list('id', flat=True))
    mask = dfData['id'].isin(existingEmployees)
    dfData.loc[mask, 'id'] = dfData['id'].astype(str) + alreadyExistsSuffix
    dfData.loc[mask, 'HasError'] = True

    #Check if the departments are correctly provided
    validDepartments = set(models.Department.objects.values_list('Name', flat=True))
    mask = ~dfData['Department'].isin(validDepartments)
    dfData.loc[mask, 'Department'] = dfData['Department'].astype(str) + errorSuffix
    dfData.loc[mask, 'HasError'] = True

    #Check if the managers are correctly provided
    validManagers = set(models.Employee.objects.values_list('id', flat=True))
    mask = ~dfData['Manager'].isin(validManagers) & dfData['Manager'].notna()
    dfData.loc[mask, 'Manager'] = dfData['Manager'].astype(str) + errorSuffix
    dfData.loc[mask, 'HasError'] = True

    #Check if the usernames are correct and don't already exist
    existingUsernames = set(User.objects.values_list('username', flat=True))
    mask1 = dfData['Username'].isin(existingUsernames) & dfData['Username'].notna()
    mask2 = dfData['Username'].astype(str).str.contains(r'\s', na=False)
    dfData.loc[mask1 | mask2, 'Username'] = dfData['Username'].astype(str) + errorSuffix
    dfData.loc[mask1 | mask2, 'HasError'] = True

    #Check if the emails are correct and don't already exist
    existingEmails = set(User.objects.values_list('email', flat=True))
    mask3 = dfData['EmailAddress'].isin(existingEmails) & dfData['EmailAddress'].notna()
    emailRegex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    mask4 = ~dfData['EmailAddress'].astype(str).str.match(emailRegex, na=True) & dfData['EmailAddress'].notna()
    dfData.loc[mask3 | mask4, 'EmailAddress'] = dfData['EmailAddress'].astype(str) + errorSuffix
    dfData.loc[mask3 | mask4, 'HasError'] = True

    dfData.loc[mask1 | mask2 | mask3 | mask4, 'UserCreation'] = dfData['UserCreation'].astype(str) + errorSuffix

    #Check if dateofbirth is valid
    dfData['DateOfBirth'] = pd.to_datetime(dfData['DateOfBirth'])
    today = pd.to_datetime('today')
    eighteenYearAgo = today - pd.DateOffset(years=18)
    mask = dfData['DateOfBirth'] >= eighteenYearAgo
    dfData['DateOfBirth'] = dfData['DateOfBirth'].dt.strftime('%d-%b-%Y')
    dfData.loc[mask, 'DateOfBirth'] = dfData['DateOfBirth'].astype(str) + errorSuffix
    dfData.loc[mask, 'HasError'] = True

    #Check if CNIC number is valid
    def validateCNIC(row: pd.Series):
        cnic = row['CNIC']
        gender = str(row['Gender']).strip().lower()

        if pd.isna(cnic) or cnic == '':
            return False
        
        pattern = r'^\d{5}-\d{7}-\d{1}$'
        if not re.match(pattern, str(cnic)):
            return True
        
        lastDigit = int(cnic[-1])
        isEven = (lastDigit % 2 == 0)

        if gender == 'male' and isEven:
            return True
        elif gender == 'female' and not isEven:
            return True

        return False

    mask = dfData.apply(validateCNIC, axis=1)
    dfData.loc[mask, 'CNIC'] = dfData['CNIC'].astype(str) + errorSuffix
    dfData.loc[mask, 'HasError'] = True

    return dfData

def formatDuration(row: pd.Index, today: datetime.timestamp):
    start = row['DateOfJoining']
    end = row['DateOfLeaving'] if pd.notnull(row['DateOfLeaving']) else today

    diff = relativedelta(end, start)

    if diff.years >= 1:
        return f"{diff.years} years"
    else:
        return f"{diff.months} months"

def GetEmployeeList():
    fields = ['id', 'WorkerName', 'Department', 'Manager__WorkerName', 'DateOfBirth', 'DateOfJoining', 'DateOfLeaving', 'Status', 'Gender']
    employees = models.Employee.objects.all().values(*fields)
    dfEmployees = pd.DataFrame(employees) if employees else pd.DataFrame(columns=fields)
    del employees

    dfEmployees.rename(inplace=True, columns={'Manager__WorkerName': 'Manager'})
    
    dfEmployees['DateOfBirth'] = pd.to_datetime(dfEmployees['DateOfBirth'])
    dfEmployees['DateOfJoining'] = pd.to_datetime(dfEmployees['DateOfJoining'])
    dfEmployees['DateOfLeaving'] = pd.to_datetime(dfEmployees['DateOfLeaving'])

    today = pd.to_datetime('today').normalize()

    dfEmployees['Age'] = (today - dfEmployees['DateOfBirth']).dt.days // 365.25

    dfEmployees['JobDuration'] = dfEmployees.apply(formatDuration, today=today, axis=1)

    return dfToListOfDicts(dfEmployees)

def GetDataForEmployeeAddition():
    fields = ['Name', 'FullName']
    departments = models.Department.objects.all().values(*fields)
    dfDepartments = pd.DataFrame(departments) if departments else pd.DataFrame(columns=fields)
    del departments
    
    fields = ['id', 'WorkerName']
    managers = models.Employee.objects.all().values(*fields)
    dfManagers = pd.DataFrame(managers) if managers else pd.DataFrame(columns=fields)
    del managers, fields

    dfDepartments.rename(inplace=True, columns={'Name': 'value', 'FullName': 'label'})

    dfManagers.rename(inplace=True, columns={'id': 'value', 'WorkerName': 'label'})
    
    data = {
        'departments': dfToListOfDicts(dfDepartments),
        'managers': dfToListOfDicts(dfManagers),
    }

    return data

def AddEmployee(data: Dict[str, any]):
    dateOfBirth = convertStrToDateTime(data.pop('DateOfBirth'), '%Y-%m-%d')
    if not dateOfBirth:
        raise ValueError('Invalid Date of Birth')
    dateOfBirth = dateOfBirth.date()
    today = TODAY.date()
    age = relativedelta(today, dateOfBirth).years
    if age < EMPLOYEMENT_AGE_IN_YEARS:
        raise ValueError(f'Minimum age for employement is {EMPLOYEMENT_AGE_IN_YEARS} years')
    
    createAccountFlag = data.pop('CreateAccount')
    userName = data.pop('Username')
    email = data.pop('Email')
    if createAccountFlag:
        if User.objects.filter(username=userName).exists():
            raise ValueError('Username already exists')
        
        if User.objects.filter(email=email).exists():
            raise ValueError('Email already exists')
    
        firstname, _, lastname = convertFullNametoNameParts(data['Name'])

        user = User.objects.create(
            username=userName,
            email=email,
            first_name=firstname,
            last_name=lastname,
        )
    else:
        user = None
    
    data['WorkerName'] = data.pop('Name')
    data['FatherSpouseName'] = data.pop('FatherSpouse')
    data['DateOfBirth'] = dateOfBirth
    data['DateOfLeaving'] = None
    data['Status'] = 'Active'
    data['User'] = user

    data['Department'] = models.Department.objects.get(Name=data['Department'])
    if data['Manager']:
        data['Manager'] = models.Employee.objects.get(id=data['Manager'])
    else:
        data['Manager'] = None
    
    employee = models.Employee(**data)
    employee.save();

    return employee.id

def PreviewUploader(file: TextIO | BinaryIO):
    dfEmployees = pd.read_excel(file) if file.name.endswith('.xlsx') else pd.read_csv(file)

    #Make sure the required columns are in the uploaded file. Ignore order of cols
    requiredCols = ['Code', 'Name', 'FatherSpouse', 'DateOfBirth', 'Department', 'SubDepartment', 'ManagerCode', 'Gender', 'CNIC', 'ShiftStart', 'ShiftEnd', 'Username', 'EmailAddress']
    if set(dfEmployees.columns) != set(requiredCols):
        missingCols = set(requiredCols) - set(dfEmployees.columns)
        extraCols = set(dfEmployees.columns) - set(requiredCols)

        if missingCols:
            raise ValueError(f'Missing Columns: {", ".join(missingCols)}')
        
        if extraCols:
            raise ValueError(f'Invalid Columns: {", ".join(extraCols)}')

    #Cache the added data to be able to use later on
    dfEmployees.rename(inplace=True, columns={
        'Code':'id',
        'Name': 'WorkerName',
        'FatherSpouse': 'FatherSpouseName',
        'ManagerCode': 'Manager'
    })
    dataTopreview = dfEmployees.to_dict(orient='records')
    cacheKey = f"workerImportCache_{uuid.uuid4()}"
    cache.set(cacheKey, dataTopreview, timeout=3600)

    dfEmployees['UserCreation'] = np.where(dfEmployees['Username'].isna(), 'No', 'Yes')

    dfEmployees = validateUploader(dfEmployees)

    dfEmployees.sort_values(inplace=True, by='HasError', ascending=False)

    return dfToListOfDicts(dfEmployees), cacheKey

def AddEmployeeBulk(token: str | None):
    if not token:
        raise ValueError('Invalid token')

    cachedData = cache.get(token)
    if cachedData is None:
        raise ValueError('Session Expired. Please try uploading again.')
    
    defaultOfficeLocation = models.Location.objects.get(id=41)

    dfData = pd.DataFrame(cachedData).copy()
    del cachedData, token

    dfUsers = dfData[['id', 'WorkerName', 'Username', 'EmailAddress']].copy()
    
    dfData.drop(inplace=True, columns=['Username', 'EmailAddress'])
    dfUsers.dropna(inplace=True, subset=['Username', 'EmailAddress'], how='all')
    if dfUsers[['Username', 'EmailAddress']].isna().all(axis=1).any():
        raise ValueError('Missing username or email address for some records')

    nameSplit = dfUsers['WorkerName'].str.split(' ', n=1, expand=True)
    if nameSplit.empty:
        nameSplit = pd.DataFrame(columns=[0,1])

    dfUsers['first_name'] = nameSplit[0]
    dfUsers['last_name'] = nameSplit[1].fillna('')
    del nameSplit
    
    dfUsers['User'] = None
    userObjs = [
        User(
            username=row['Username'],
            email=row['EmailAddress'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            is_active=True
        ) for _, row in dfUsers.iterrows()
    ]
    
    with transaction.atomic():
        createdUsers = User.objects.bulk_create(userObjs)
        dfUsers['User'] = createdUsers
    
    dfUsers.drop(inplace=True, columns=['Username', 'WorkerName', 'EmailAddress', 'first_name', 'last_name'])
    dfData = pd.merge(left=dfData, right=dfUsers, on='id', how='left')
    del dfUsers

    dfData['Manager'] = np.where(dfData['Manager'].isna(), None, dfData['Manager'])
    dfData['User'] = np.where(dfData['User'].isna(), None, dfData['User'])
    dfData['DateOfBirth'] = np.where(dfData['DateOfBirth'].isna(), None, dfData['DateOfBirth'])
    
    dfData['DateOfBirth'] = pd.to_datetime(dfData['DateOfBirth'], unit='ns')
    dfData['DateOfBirth'] = dfData['DateOfBirth'].dt.date

    genderMap = {
        'M': 'Male',
        'F': 'Female',
    }    
    dfData['Gender'] = dfData['Gender'].map(genderMap)

    dfData['Department'] = convertTexttoObject(models.Department, dfData['Department'], 'Name')
    dfData['Manager'] = convertTexttoObject(models.Employee, dfData['Manager'], 'id')

    employeesToAdd = []
    assignmentsToAdd = []
    for _, row in dfData.iterrows():
        employee = models.Employee(**row)
        employeesToAdd.append(employee)

        locatoinAssignment = models.LocationAssignment(
            Employee=employee,
            Location=defaultOfficeLocation
        )
        assignmentsToAdd.append(locatoinAssignment)

    #models.Employee.objects.bulk_create(employeesToAdd)
    #models.LocationAssignment.objects.bulk_create(assignmentsToAdd)

    raise NotImplementedError('Under Construction')

    return len(employeesToAdd)

def GetDataForEmployeeUpdate(employee: models.Employee):
    employeeData = model_to_dict(employee)
    employeeData.update({
        'Name': employeeData.pop('WorkerName', None),
        'FatherSpouse': employeeData.pop('FatherSpouseName', None),
        'CreateAccount': bool(employee.User)
    })

    if employee.User:
        employeeData['Username'] = employee.User.username
        employeeData['Email'] = employee.User.email
    else:
        employeeData['Username'] = None
        employeeData['Email'] = None
    
    employeeData['SubDepartment'] = employeeData['SubDepartment'] if employeeData['SubDepartment'] else ''

    departments = list(
        models.Department.objects.values(value=F('Name'), label=F('FullName'))
    )
    
    managers = list(
        models.Employee.objects.values(value=F('id'), label=F('WorkerName'))
    )

    data = {
        'employeeData': employeeData,
        'departments': departments,
        'managers': managers,
    }

    return data

def UpdateEmployee(employee: models.Employee, data: Dict[str, str | int | None]):
    createUserAccountFlag = data.pop('CreateAccount', False)

    if createUserAccountFlag:
        user = data.get('User')
        email = data.get('Email')
        firstname, _, lastname = convertFullNametoNameParts(data['Name'])

        if user and User.objects.filter(id=user).exists():
            user = User.objects.get(id=user)
            if models.Employee.objects.filter(User=user).exclude(id=employee.id).exists():
                raise ValueError('This user is already assign to another employee')
        else:
            user = User.objects.create_user(
                username=email, 
                email=email, 
                first_name=firstname,
                last_name=lastname,
            )
        
        employee.user = user
    else:
        if employee.User:
            employee.User = None
    data.pop('User')
    data.pop('Email')
    data.pop('Username')
    
    customFieldMapping = {
        'Name': 'WorkerName',
        'FatherSpouse': 'FatherSpouseName',
    }
    if data['Manager']:
        try:
            data['Manager'] = models.Employee.objects.get(id=data['Manager'])
        except:
            raise LookupError('Cannot find manager')
    try:
        data['Department'] = models.Department.objects.get(Name=data['Department'])
    except:
        raise LookupError('Invalid department')
    
    data['DateOfBirth'] = datetime.fromisoformat(data['DateOfBirth'].replace("Z", "+00:00")).date()
    if data['DateOfLeaving']:
        data['DateOfLeaving'] = datetime.fromisoformat(data['DateOfLeaving'].replace("Z", "+00:00")).date()
        data['Status'] = 'Left'
    else:
        data['Status'] = employee.Status
    
    for key, value in data.items():
        fieldName = customFieldMapping.get(key, key)

        if hasattr(employee, fieldName):
            setattr(employee, fieldName, value)
    
    employee.save()