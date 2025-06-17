import pandas as pd
import numpy as np

from django.http import HttpRequest
from django_countries import countries

from .. import models
from core.services.generic_services import askAI, dfToListOfDicts, updateModelWithDF

def getCountryName(code: str):
    """Get the country name from it's country code. If code isn't found, then None is returned."""
    try:
        return countries.name(code)
    except KeyError:
        return None   

def GetCustomers(
        request: HttpRequest,
        assignFilter: str,
        countryFilter: str
):
    if assignFilter == 'Active':
        customers = models.Customer.objects.filter(AccountManager=request.user)
    else:
        customers = models.Customer.objects.filter(AccountManager = None)

    if countryFilter:
        customers = customers.filter(Country=countryFilter)

    fields = ['id','Name','Country','Website','Address']
    customers = customers.values(*fields)
    if customers:
        dfCustomers = pd.DataFrame(customers)
    else:
        dfCustomers = pd.DataFrame(columns=fields)
    del customers

    fields = ['Customer', 'Name', 'Designation', 'IsActive', 'PhoneNumber', 'Email']
    customerContacts = models.CustomerContact.objects.filter(Customer__in=dfCustomers['id'].to_list()).values(*fields)
    if customerContacts:
        dfCustomerContacts = pd.DataFrame(customerContacts)
    else:
        dfCustomerContacts = pd.DataFrame(columns=fields)
    del fields, customerContacts

    dfCustomers['Country'] = dfCustomers['Country'].apply(getCountryName)
    dfCustomers = dfCustomers.sort_values(by='Country').reset_index(drop=True)

    # Combine Name and Designation to ContactDetails
    dfCustomerContacts['ContactDetails'] = dfCustomerContacts['Name'] + np.where(dfCustomerContacts['Designation'].str.len() > 0,
                                                                                  ' (' + dfCustomerContacts['Designation'] + ')',
                                                                                  '')

    # Add phone number
    dfCustomerContacts['ContactDetails'] = dfCustomerContacts['ContactDetails'] + np.where(dfCustomerContacts['PhoneNumber'].str.len() > 0,
                                                                                             ' (Ph: ' + dfCustomerContacts['PhoneNumber'] + ')',
                                                                                             '')

    # Add email
    dfCustomerContacts['ContactDetails'] = dfCustomerContacts['ContactDetails'] + np.where(dfCustomerContacts['Email'].str.len() > 0,
                                                                                             ' (Email: ' + dfCustomerContacts['Email'] + ')',
                                                                                             '')

    # Add InActive status
    dfCustomerContacts['ContactDetails'] = np.where(dfCustomerContacts['IsActive'] == False,
                                                                 dfCustomerContacts['ContactDetails'] + ' (InActive)',
                                                                 dfCustomerContacts['ContactDetails'])

    # Drop the original columns to improve performance
    dfCustomerContacts.drop(inplace=True, columns=['Name', 'Designation', 'PhoneNumber', 'Email', 'IsActive'])
    dfCustomerContacts = dfCustomerContacts.groupby('Customer')['ContactDetails'].apply(list).reset_index()

    dfCustomerContacts.rename(inplace=True, columns={'Customer':'id'})

    dfCustomers = pd.merge(left=dfCustomers, right=dfCustomerContacts, left_on='id', right_on='id', how='left')
    del dfCustomerContacts

    dfCustomers['ContactDetails'] = np.where(dfCustomers['ContactDetails'].isna(), '', dfCustomers['ContactDetails'])

    data = dfToListOfDicts(dfCustomers)

    listOfCountries = [{'value':None, 'text': 'All Countries'}]
    for code, name in list(countries):
        listOfCountries.append({'value': code, 'text': name})

    return data, listOfCountries

def AddCustomer(dfCustomer: pd.DataFrame, dfCustomerDetails: pd.DataFrame):
    #Raise error if customer name isn't provided
    dfCustomer = dfCustomer[dfCustomer['Name'].str.len()>0]
    if dfCustomer.empty:
        raise ValueError('No Customer provided')    
    
    #Remove rows where customer details aren't provided
    mask = (dfCustomerDetails[dfCustomerDetails.columns].astype(str).apply(lambda row: row.str.len() == 0, axis=1)).all(axis=1)
    dfCustomerDetails = dfCustomerDetails[~mask]

    previousCustomers = models.Customer.objects.all().values('Name','Website')
    customer = dfCustomer.iloc[0].to_dict()

    queryStrings = [
        f"Name: {previousCustomer['Name']} | Website: {previousCustomer['Website']}" for previousCustomer in previousCustomers
    ]
    del previousCustomers

    queryStrings = ", ".join(queryStrings)
    question = f"True or False, is {customer['Name']} in the given list of companies? {queryStrings}?"

    answer = askAI(question)
    del question, queryStrings

    if 'True' in answer:
        raise ValueError('Customer already exists')
    del answer
    
    customer = models.Customer(**customer)
    customer.AccountManager = None
    customer.save()
    
    for _, row in dfCustomerDetails.iterrows():
        customerContact = models.CustomerContact(**row.to_dict())
        customerContact.Customer = customer
        customerContact.IsActive = True
        
        customerContact.save()
    
    return customer.id

def GetDataForCustomer (customer: models.Customer):
    customerData = {
        'Name': customer.Name,
        'Website': customer.Website,
        'Address': customer.Address,
        'Country': customer.Country,
        'AccountManager': customer.AccountManager.username if customer.AccountManager else None,
    }

    fields = ['id','Name','Designation','IsActive', 'PhoneNumber','Email']
    customerContacts = models.CustomerContact.objects.filter(Customer=customer).values(*fields)
    if customerContacts:
        dfCustomerContacts = pd.DataFrame(customerContacts)
    else:
        dfCustomerContacts = pd.DataFrame(columns=fields)
    del fields, customerContacts

    return customerData, dfToListOfDicts(dfCustomerContacts)

def EditCustomer(
        customer: models.Customer,
        dfCustomer: pd.DataFrame,
        dfCustomerDetails: pd.DataFrame
):
    customerData = dfToListOfDicts(dfCustomer)[0]
    del dfCustomer
    if len(customerData['Name']) < 1:
        raise ValueError('Customer Name is mandatory')
    
    #Remove rows where customer details aren't provided
    mask = (dfCustomerDetails[dfCustomerDetails.columns.to_list()[:-1]].astype(str).apply(lambda row: row.str.len() == 0, axis=1)).all(axis=1)
    dfCustomerDetails = dfCustomerDetails[~mask]

    for field, value in customerData.items():
        setattr(customer, field, value)
    del customerData
    customer.save()

    fields = ['id']
    previousContact = models.CustomerContact.objects.filter(Customer=customer).values(*fields)
    if previousContact:
        dfPreviousContacts = pd.DataFrame(previousContact)
    else:
        dfPreviousContacts = pd.DataFrame(columns=fields)
    del fields, previousContact

    dfCustomerDetails['Customer'] = customer

    dfCustomerDetails['id'] = np.where(dfCustomerDetails['id'].str.len()==0, None, dfCustomerDetails['id'])

    updateModelWithDF(models.CustomerContact, dfCustomerDetails, dfPreviousContacts) 