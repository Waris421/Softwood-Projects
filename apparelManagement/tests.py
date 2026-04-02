from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from . import models

import json

import json

class TestViews(TestCase):
    def setUp(self):
        self.targetUrl = reverse('copyWO', kwargs={'pk':12345})   

        customer = models.Customer.objects.create(
            Name = 'TestCustomer',
            TradeName = 'Testing'
        )
        customer.save()
        
        unitGroup = models.UnitGroup.objects.create(
            Name = 'TestunitGroup',
            StandardUnit = 'TestGroup'
        )
        unitGroup.save()

        unit = models.Unit.objects.create(
            Name = 'TestGroup',
            Group = unitGroup,
            Factor = 1,
        )
        unit.save()

        #Create a testing style
        style = models.StyleCard.objects.create(
            StyleCode = 'TestStyle',
            StyleName = 'Testing',
            Customer = customer,
            Category = 'Men',
            Notes = 'ABCD'
        )
        style.save()

        currency = models.Currency.objects.create(
            Code = 'Test',
            Name = 'Test Currency',
            IsLocal = False,
        )
        currency.save()

        #Create a variant for the test style
        models.StyleVariant.objects.create(
            Style = style,
            VariantCode = 'Testing'
        ).save()

        #Create a user in marketing department.
        marketingUser = User.objects.create_user(
            username = 'marketing@example.com',
            email = 'testuser@example.com',
            password = 'password123',
        )
        marketingUser.save()
        marketingGroup = Group.objects.create(name='Marketing')
        marketingGroup.save()
        marketingUser.groups.add(marketingGroup)
        
        productionUser = User.objects.create_user(
            username = 'production@example.com',
            email = 'testuser1@example.com',
            password = 'password12312',
        )
        productionUser.save()
        productionGroup = Group.objects.create(name='Production')
        productionGroup.save()   
        productionUser.groups.add(productionGroup)
        
        #Create a fake browser and login using the test user
        self.client = Client()
        self.client.force_login(marketingUser)

        order = models.WorkOrder.objects.create(
            OrderNumber = '12345',
            StyleCode = style,
            Customer = customer,
            OrderDate = '2025-01-31',
            Merchandiser = marketingUser,
            DeliveryDate = '2025-03-31',
            Type = 'Export',
            Currency = currency,
            Price = 12.0,
            Agent = 'Test',
            Commission = 5.0,
            ExcessCut = 3.0
        )
        order.save()

    def testUpdateWO (self):   
        data = {
            'receipt_PONumber': '75', 'receipt_Invoice': '', 'receipt_Vehicle': '', 'receipt_Bilty': '', 'receipt_BiltyValue': '0',
            'inventory_InvCode_1': 'THRNB202008625', 'inventory_Variant_1': '', 'inventory_Quantity_1': '42',
            'inventory_InvCode_2': 'THRNB203008625', 'inventory_Variant_2': '', 'inventory_Quantity_2': '28'
        }

        response = self.client.post(
            path=self.targetUrl,
            data=data)
        
        notifications = models.Notification.objects.all().values()

        print(notifications)

        self.assertEqual(response.status_code, 302)
