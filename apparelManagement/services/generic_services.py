import pandas as pd
import numpy as np

from pytz import timezone
import datetime
from collections import defaultdict
from typing import Dict, Any, List

from django.db.models import Model
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.models import User

from rest_framework.request import Request
from rest_framework.authtoken.models import Token

LOCAL_TIMEZONE = timezone('Asia/Karachi')
GST_RATE = 18.0
LOCAL_CURRENCY = 'PKR'

def updateModelWithDF (
        targetTable: Model,
        newData: pd.DataFrame,
        previousData: pd.DataFrame,
):
    '''
    Update a django model with the new data provided in dataframe.
    Rows present in the preiousData but not in newData would be deleted.
    Rows present in both new and previous data would be updated.
    Rows present in newData but not in previousData would be created.
    Both newData and preiousData must have an id column
    '''
    if not previousData.empty:
        #Find out entries that are present in dfPrevious but not in dfNew. These are the one's deleted by user
        dfDeleted = previousData[~previousData['id'].isin(newData['id'])]
        
        #Delete the entries from database that are deleted by user
        for _, row in dfDeleted.iterrows():
            targetTable.objects.get(id=row.id).delete()
        del dfDeleted, previousData

    #Set any rows as new entries where id is nan
    newData['id'] = np.where(newData['id'].isna(), None, newData['id'])

    #add new entries and update the already existing one
    for _, row in newData.iterrows():
        try:
            #Connect to the previuos entry from database. If not found, create new.
            previousEntry, newEntryFlag = targetTable.objects.get_or_create(id=row.id, defaults=row.to_dict())
        except Exception as e:
            #Show any error message to user
            raise ValueError(e)

        #Move to next iteration if this is a new entry
        if newEntryFlag:
            continue
        
        #Replace each column of the row other than id with the newly provided data
        for key, value in row.items():
            if key != 'id':
                setattr(previousEntry, key, value)
        
        #Save the entry
        previousEntry.save()

def refineJson(jsonData: Dict[str, Any]) -> pd.DataFrame | List[pd.DataFrame]:
    '''
    Refine the data from form into corresponding dataframes.
    '''
    #Create a default dict, so if any keys are missing, they'll be created.
    groupedData = defaultdict(dict)
    
    #Separate the data of each groups, based on the first part of key
    for key, value in jsonData.items():
        prefix = key.split('_')[0]
        groupedData[prefix][key] = value
    del jsonData

    #Define an empty list of tables that would contain each table's data separately
    dfs = []
    
    for _, groupData in groupedData.items():        
        #Create a default dict for the data rows, so if any keys are missing, they'll be created.
        dataRows = defaultdict(dict)

        for key, value in groupData.items():
            #Split the name of the key, to group, column and row
            nameParts = key.split('_')

            #Key must have at least table and column name
            if len(nameParts) < 2:
                raise KeyError('Invalid Format')
            
            if nameParts[-1].isdigit():
                #Last part of the name is a number, meaning that a row number is provided
                rowNum = int(nameParts[-1])
                colName = '_'.join(nameParts[1:-1])
            else:
                #Last part of name is text, meaning that only column name is provided.
                #This must only be done for single row entries, otherwise it'll ignore all but last row
                rowNum = 1
                colName = '_'.join(nameParts[1:])
            #Set the value in the given row and col
            dataRows[rowNum][colName] = value
        
        #Create a dataframe from the dict of the group's data
        df = pd.DataFrame.from_dict(dataRows, orient='index')

        #Reset the rows, so that they start from 0
        df = df.reset_index(drop=True)

        #Replace any null values with None
        df = df.replace('null',None)
        
        #Append the dataframe to the list of dataframes
        dfs.append(df)
    if len(dfs) == 1:
        return dfs[0]
    else:
        return dfs

def convertTexttoObject (model: Model, column: pd.Series, fieldName: str) -> pd.Series:
    '''
    Converts a pandas Series of values to a Series of corresponding Django model objects.
    Ignores missing values. Preserves original series order.
    '''
    #remove any NA, NaN, NAT, Blank values from the column and remove duplicates
    validValues = column.dropna().unique()

    if validValues.size == 0:
        return pd.Series([None] * len(column), index=column.index)

    #Get the relevance objects from the models in one query and convert to a dict
    objectsDict = {
        getattr(obj, fieldName): obj 
        for obj in model.objects.filter(**{f"{fieldName}__in": validValues})
    }

    return column.map(objectsDict.get)

def concatenateValues(column: pd.Series, limit=3):
    '''
    Combine the text in a column to one string.
    By default it will take first three distinct values

    If there is no valid value the column, it'll return None
    '''
    #Remove an invalid values from the column
    validValues = [str(x).strip() for x in column.dropna() if str(x).strip()]
    
    #Remove duplicates from the values
    distinctValues = list(set(validValues))

    #Select only the first n values
    subSet = distinctValues[:limit]
    
    #Return values after joining them by comma
    return ', '.join(subSet) if subSet else None

def paginate (data: List[Any], pageNumber: Any, numOfRows: int = 50):
    '''
    Paginates data for a Django webpage and return the data at the provided page number.
    Default number of rows per page is 50, but can be changed.
    '''
    #Convert data into pages, containing the provided row numbers per page
    paginator = Paginator(data, numOfRows)
    
    try:
        #Convert page number to int, if possible, other wise 1
        pageNumber = int(pageNumber) if pageNumber else 1

        #Go the provided page number
        page = paginator.page(pageNumber)
    except PageNotAnInteger:
        #Go to first page if invalid page number is provided
        page = paginator.page(1)
    except EmptyPage:
        #Go to last page if there is no data in the page
        page = paginator.page(paginator.num_pages) if paginator.num_pages > 0 else paginator.page(1)
    except Exception as e:
        #Show error to user
        raise IndexError(e)

    #Return the selected page
    return page

def applySearch (data: List[Dict], searchTerm: str) -> List[Dict]:
    '''Filters a list of dictionaries, returning only those dicts that contain the 
    search term (case-insensitive) in any of their values.'''
    
    #Convert the search term to lower case
    searchTerm = searchTerm.lower()
    
    #Initialize an empy list.
    results = []
    
    #Iterate though each element of the data list
    for row in data:
        #Set flag to true, if the serach term is found in any value of item dict.
        flag = any(searchTerm in str(cell).lower() for cell in row.values())
        
        #Add the list item to results if ihe flag is true
        if flag:
            results.append(row) 

    #Return the results list of dicts, which would contain the filtered values
    return results

def truncateTime (time: datetime.time):
    '''
    Remove microseconds part from a time object
    '''
    if time is None:
        return None
    return time.replace(microsecond=0)

def getAPIUser(request: Request) -> User:
    credentials = request.data.get('credentials')
    
    try:
        token = Token.objects.get(key=credentials)
        return token.user
    except:
        raise PermissionError('Unauthorised')