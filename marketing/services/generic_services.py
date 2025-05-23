from apparelManagement.services.generic_services import convertTexttoObject, paginate, applySearch, truncateTime, getAPIUser
from apparelManagement.services.generic_services import refineJson, concatenateValues, updateModelWithDF, LOCAL_TIMEZONE

from google import genai
import pandas as pd

import os

API_KEY_FOR_AI = os.environ.get("API_KEY_FOR_AI")

def askAI(question: str):
    '''
    Ask AI a question and get it's answer
    '''
    client = genai.Client(api_key=API_KEY_FOR_AI)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=question,
    ).text

    return response

def dfToListOfDicts(df: pd.DataFrame):
    '''
    Converts a dataframe to a list of dicts
    '''
    if df.empty:
        return []
    else:
        return df.to_dict(orient='records')