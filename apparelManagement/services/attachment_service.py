import pandas as pd
import numpy as np
from typing import TypeVar

from .. import models

modelT = TypeVar("ModelT", bound=models.models.Model)

def updateAttachmentsFromDF(
    instance: modelT,
    newData: pd.DataFrame,
    previousData: pd.DataFrame,
):
    newData['id'] = newData['id'].replace('', np.nan)
    newData['id'] = pd.to_numeric(newData['id'], errors='coerce').astype('Int64')
    newData['id'] = newData['id'].where(newData['id'].notnull(), None)

    updateFields = ['Description']

    deletedAttachments = set(previousData['id']) - set(newData['id'].dropna())
    deletedAttachments = models.Attachment.objects.filter(id__in=deletedAttachments)

    attachmentsToCreate = []
    attachmentsToUpdate = []

    for _, row in newData.iterrows():
        if pd.notna(row['id']):
            rowDict = row.to_dict()
            
            attachment = models.Attachment.objects.get(id=rowDict.pop('id'))

            for key, value in rowDict.items():
                setattr(attachment, key, value)
            attachmentsToUpdate.append(attachment)
        else:
            row['id'] = None
            row['Content'] = instance
            attachment = models.Attachment(**row)
            attachmentsToCreate.append(attachment)

    if deletedAttachments:
        deletedAttachments.delete()
    
    models.Attachment.objects.bulk_create(attachmentsToCreate)
    models.Attachment.objects.bulk_update(attachmentsToUpdate, updateFields)