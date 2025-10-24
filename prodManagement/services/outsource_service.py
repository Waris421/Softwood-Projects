import pandas as pd
import numpy as np

from django.db.models import Q

from .. import models

from core.services.generic_services import dfToListOfDicts

def GetOutsourceContracts(workOrder: str, source: str, contractNumber: str, approval: str):
    print('I am called')


def AddContract(dfHeading: pd.DataFrame, dfDetails: pd.DataFrame):
    heading = dfHeading.iloc[0].to_dict()
    
    for key, value in heading.items():
        if not value:
            raise ValueError(f'Missing {key}')
    
    print(dfDetails['WorkOrder'])
    
    source = heading.pop('Source')
    contract = models.OutSourceJobContract(**heading)

    for _, row in dfDetails.iterrows():
        workOrder=row['WorkOrder']
        styleRoute = row['Operation']
        try:
            productionPlan = models.ProductionPlan.objects.get(
                WorkOrder=workOrder,
                StyleRoute = styleRoute,
            )
        except:
            stage = models.StyleRoute.objects.get(id=styleRoute).Stage
            raise ImportError(f'Order:{workOrder} Operation:{stage} is not currently planned.')
        
        contractDetails = models.OurSourceJobContractDetails(
            OutSourceJobContract=contract,
            ProductionPlan=productionPlan,
            print=row['Price']
        )
        print(contractDetails)

    raise NotImplementedError('Under Construction')