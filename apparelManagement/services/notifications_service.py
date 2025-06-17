import pandas as pd

from django.contrib.auth.models import User, Group
from django.db.models import Sum

from typing import Dict
import warnings

from .. import models
from core.services.generic_services import truncateTime

def createNotifications (notification: Dict, groupName: 'str'):
    '''
    Create the given notification for all the users in the given group. Will warn if group is empty
    '''
    #Get all active users in the provided group
    #TODO: remove the try,except in production
    try:
        users = Group.objects.get(name=groupName).user_set.filter(is_active=True)
    except:
        return
    
    if not users:
        warnings.warn(f'{groupName} department has no active members',UserWarning)

    bulkNotifications = []
    for user in users:
        notification ['User'] = user
        notification = models.Notification(**notification)
        bulkNotifications.append(notification)
    
    models.Notification.objects.bulk_create(bulkNotifications)

def GetNotifications (user: User):
    notifications = models.Notification.objects.filter(IsRead=False).filter(User=user).values('id','Heading','Summary','DateTime')
    if notifications:
        dfNotifications = pd.DataFrame(notifications)
    else:
        return []
    del notifications

    dfNotifications['DateTime'] = dfNotifications['DateTime'].apply(truncateTime)

    dfNotifications.rename(inplace=True, columns={'Heading':'title','Summary':'body'})
    
    now = pd.to_datetime('now', utc=True)
    dfNotifications['SecondsPassed'] = (now - dfNotifications['DateTime']).dt.total_seconds()
    del now
    dfNotifications.drop(inplace=True, columns=['DateTime'])

    dfNotifications['timePassed'] = dfNotifications['SecondsPassed'].apply(formatTime)
    dfNotifications.drop(inplace=True, columns=['SecondsPassed'])

    dfNotifications['width'] = dfNotifications['body'].apply(calculateWidth)
 
    #This converts the dataframe back to list of dicts so it can be shown to user
    cols = [i for i in dfNotifications]
    data = [dict(zip(cols, i)) for i in dfNotifications.values]
    return data

def GetNotificationDetails(id: int):
    notification = models.Notification.objects.get(id=id)
    
    notification = {
        'id': notification.id,
        'title': notification.Heading,
        'body': notification.Body,
        'url': notification.URL,
    }

    return notification

def ReadNotification (id: int, user: User):
    try:
        notification = models.Notification.objects.get(id=id)
    except:
        raise ValueError ('Resource not found')
    
    if user != notification.User:
        raise PermissionError ('Access denied')
    
    notification.IsRead = True
    notification.save()

def formatTime (timeinSeconds: float):
    '''
    Converts time in seconds to human readable time.
    '''
    if timeinSeconds < 60:
        return f"{round(timeinSeconds)}sec"
    elif timeinSeconds < 3600:
        timeInMinutes = round(timeinSeconds / 60)
        return f"{timeInMinutes}min"
    elif timeinSeconds < 86400:
        timeInHours = round(timeinSeconds / 3600)
        return f"{timeInHours}hr"
    else:
        timeInDays = round(timeinSeconds / 86400)
        return f"{timeInDays}d"

def calculateWidth(string: str):
    '''
    Calculate the width of notification box based on the length of it's body
    '''
    if len(string) < 20:
        return 2
    elif len(string) > 200:
        return 12
    else:
        width = int((len(string) - 20) / 180 * 10 + 2)
        return width

def AddWorkOrder (orderNumber: int):
    workOrder = models.WorkOrder.objects.get(OrderNumber=orderNumber)
    quantity = models.OrderVariant.objects.filter(OrderNumber=workOrder).values('Quantity').aggregate(quantity=Sum('Quantity'))
    quantity = quantity['quantity']

    notification = {
        'Heading': 'Order Received',
        'Summary': f'Order#{workOrder.OrderNumber}',
        'Body': f'Work Order # {workOrder.OrderNumber}, DeliveryDate: {workOrder.DeliveryDate}, quantity: {quantity}',
        'URL': f'/workorder/{workOrder.OrderNumber}/edit',
        'IsRead': False
    }

    createNotifications (notification, 'Production')

def DeleteWorkOrder (workOrder: models.WorkOrder, orderNumber: int):
    notification = {
        'Heading': 'Order Cancelled',
        'Summary': f'Order#{orderNumber}',
        'Body': f'Work Order # {orderNumber}, Customer: {workOrder.Customer.Name}',
        'URL': '',
        'IsRead': False
    }

    createNotifications (notification, 'Production')