"""
Contains generic functions
"""

import pandas as pd
import numpy as np
import json

from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Union

import google.generativeai as genai

from django.db import transaction
from django.db.models import Model
from django.db import models as dbModels
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpRequest
from django.shortcuts import render
from django_countries import countries

from core.constants.generic import API_KEY_FOR_AI
from core.services.auth_service import getNavLinks
from core.constants.theme import theme

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
    if 'id' not in newData.columns:
        raise ValueError("id columns are missing in newData df.")
    
    if 'id' not in newData.columns:
        raise ValueError("id columns are missing in previousData df.")

    if not previousData.empty:
        #Find out entries that are present in dfPrevious but not in dfNew. These are the one's deleted by user
        deletedIds = previousData[~previousData['id'].isin(newData['id'])]['id'].tolist()

        if deletedIds:
            targetTable.objects.filter(id__in=deletedIds).delete()

    #Set any rows as new entries where id is nan
    newData['id'] = np.where(newData['id'].isna(), None, newData['id'])

    #Any data in newData who have id. These would be the data already existing in the db and updated by user
    dfExistingNewData = newData[newData['id'].notna()]
    
    # Get a list of existing IDs from the database that are also in our new data
    existingNewDataIds = set(targetTable.objects.filter(id__in=dfExistingNewData['id'].tolist()).values_list('id', flat=True))

    toCreate = []
    toUpdate = []

    for _, row in newData.iterrows():
        # Exclude 'id' for creation if it's new
        rowDict = row.drop('id', errors='ignore').to_dict()

        if row['id'] in existingNewDataIds:
            #Existing Entry. Need to update the DB
            obj = targetTable(**row.to_dict())
            toUpdate.append(obj)
        else:
            #New Entry. Need to add to DB
            toCreate.append(targetTable(**rowDict))

    #This ensures that the code below it is part of one db transation. If any one part of transaction fails, it calls back all changes made.
    with transaction.atomic():
        if toCreate:
            targetTable.objects.bulk_create(toCreate)

        if toUpdate:
            # Update only those cols that are provided by user. Exclude fields like 'id'.
            fieldsToUpdate = [col for col in newData.columns if col != 'id']
            
            targetTable.objects.bulk_update(toUpdate, fields=fieldsToUpdate)

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

    #Iterate though each element of the data list
    results = [
        row for row in data
        if any(searchTerm in str(value).lower() for value in row.values())
    ]

    return results

def truncateTime (time: datetime.time):
    '''
    Remove microseconds part from a time object
    '''
    if time is None:
        return None
    return time.replace(microsecond=0)

def convertStrToDateTime(date: str, format: str):
    return datetime.strptime(date, format)

def askAI(prompt: str, outputSchema: Union[Dict[str, Any], None] = None):
    '''
    Ask AI a question and get it's answer
    '''
    genai.configure(api_key=API_KEY_FOR_AI)

    model = genai.GenerativeModel(model_name='gemini-2.0-flash')

    if outputSchema:
        schemaDescription = ", ".join([f"{k}: {v.__name__}" for k, v in outputSchema.items()])
        prompt = (
            f"{prompt}\n\n"
            f"Please provide the response in a JSON array format, where each object "
            f"in the array has the following keys and types: {schemaDescription}. "
            f"Ensure the output is a valid JSON array."
        )
        response = model.generate_content(prompt)
        responseText = response.text
        parsedData = json.loads(responseText)

        if isinstance(parsedData, list):
            return parsedData
        else:
            raise ValueError('Could not get the response in the required format.')
    else:
        response = model.generate_content(prompt)
        return response.text

def dfToListOfDicts(df: pd.DataFrame):
    '''
    Converts a dataframe to a list of dicts
    '''
    if df.empty:
        return []
    else:
        return df.to_dict(orient='records')

def showMessageResponse(request: HttpRequest, message: str, statusCode=400):
    context = {
        'message': message,
        'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render(request, 'blank.html', context, status=statusCode)

def convertCountryNameToCode(countryNamesSeries: pd.Series):
    countryNames = countryNamesSeries.unique().tolist()

    genai.configure(api_key=API_KEY_FOR_AI)

    prompt = f"""
    Convert the following list of country names to their respective ISO 3166-1 alpha-2 codes.
    If a country name is misspelled, please do your best to identify the correct country and provide its ISO code.
    Return the output as a JSON array of objects, where each object has a 'countryName' field (the original input country name) and an 'isoCode' field (the corresponding ISO 3166-1 alpha-2 code).
    If a country cannot be identified, return 'null' for its 'isoCode'.

    Country names: {json.dumps(countryNames)}
    """

    responseSchema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "countryName": {"type": "STRING"},
                "isoCode": {"type": "STRING", "nullable": True}
            },
            "required": ["countryName", "isoCode"]
        }
    }

    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": responseSchema
        }
    )

    response = model.generate_content(prompt)

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        jsonString = response.candidates[0].content.parts[0].text
        isoCodesList = json.loads(jsonString)
        isoCodesMap = {item['countryName']: item['isoCode'] for item in isoCodesList}
        return isoCodesMap
    else:
        raise LookupError('An error occured while converting countries')

def convertCountryCodeToName(code):
    try:
        return dict(countries)[code]
    except:
        return None