from apparelManagement.services.generic_services import convertTexttoObject, paginate, applySearch, truncateTime, getAPIUser
from apparelManagement.services.generic_services import refineJson, concatenateValues, updateModelWithDF, LOCAL_TIMEZONE

from google import genai
from google.generativeai.types import GenerationConfig
import pandas as pd

import os
from typing import Dict, Any

API_KEY_FOR_AI = os.environ.get("API_KEY_FOR_AI")

def askAI(question: str, outputSchema: Dict[str, Any]=None):
    '''
    Ask AI a question and get it's answer
    '''
    client = genai.Client(api_key=API_KEY_FOR_AI)
    
    config = GenerationConfig(
        response_mime_type="text/x.enum",
    )

    if outputSchema:
        config.response_schema = outputSchema

    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=question,
        config=config,
    )
    return response.text

def dfToListOfDicts(df: pd.DataFrame):
    '''
    Converts a dataframe to a list of dicts
    '''
    if df.empty:
        return []
    else:
        return df.to_dict(orient='records')