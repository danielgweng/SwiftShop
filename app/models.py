from flask_login import UserMixin
import boto3
from app import login, mail, mail_settings
from ebaysdk.exception import ConnectionError
from ebaysdk.finding import Connection as Finding
from ebaysdk.shopping import Connection as Shopping
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from datetime import datetime
import requests
import json
from flask_mail import Message

class User(UserMixin):
    def __init__(self):
        self.id = -1
        self.username = ""
        self.encrypted_pass = ""
        self.email = ""

    def __repr__(self):
        return '<ID {} User {} Encrypted Pass {} Email {}>'.format(self.id, self.username, self.encrypted_pass, self.email)

class EmailManager:
    def __init__(self):
        self.mail_settings = mail_settings

    def send_email(self, subject, sender, recipients, body, html):
        msg = Message(subject=subject, sender=sender, body=body, recipients=recipients, html=html)
        mail.send(msg)

class DynamoDBManager:
    def __init__(self):
        self.db = boto3.resource('dynamodb', region_name='us-east-1',
                                 endpoint_url="https://dynamodb.us-east-1.amazonaws.com")
        self.users_table = self.db.Table('UsersAndSearchResults')

    def register_new_user(self, username, encryptedpass, unique_id, email):
        print("registering..")
        item = {
            "UserName": username,
            "Password": encryptedpass,
            "Email": email,
            "id": unique_id,
            "BarcodesInfo": [],
            "SearchHistory": [],
            "cartItems": []
        }
        self.users_table.put_item(Item=item)
        print(item)

    def get_user_data(self, username):
        try:
            response = self.users_table.get_item(Key={
                'UserName': username,
            })
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            if 'Item' in response.keys():
                item = response['Item']
                print("GetItem succeeded:")
                return item
            else:
                return None

    def update_user_data(self, username, data):
        response = self.users_table.update_item(Key={
            'UserName': username
        },
            UpdateExpression="set data=:i",
            ExpressionAttributeValues={
                ':i': data
            },
            ReturnValues="UPDATED_NEW")
        print("UpdateItem succeeded:")

    def update_user_data_attribute(self, username, key, value):
        response = self.users_table.update_item(
            Key={
                'UserName': username
            },
            UpdateExpression="set data.{} = :x".format(key),
            ExpressionAttributeValues={
                ':x': value
            },
            ReturnValues="UPDATED_NEW"
        )

        print("UpdateItem succeeded:")

    def update_append_user_search_history_attribute(self, username, search_type, query, items):
        response = self.users_table.update_item(
            Key={
                'UserName': username
            },
            UpdateExpression="SET SearchHistory = list_append(SearchHistory, :i)",
            ExpressionAttributeValues={
                ':i': [
                    {
                        "SearchType": search_type,
                        "TimeStamp": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                        "Items": items,
                        "Query": query
                    }
                ]
            },
            ReturnValues="UPDATED_NEW"
        )

    def update_append_user_barcode_attribute(self, username, barcode_value, stored_photo):
        response = self.users_table.update_item(
            Key={
                'UserName': username
            },
            UpdateExpression="SET BarcodesInfo = list_append(BarcodesInfo, :i)",
            ExpressionAttributeValues={
                ':i': [
                    {
                        "Barcode": barcode_value,
                        "StoredPhoto": stored_photo,
                        "TimeStamp": datetime.now().strftime('%Y-%m-%d-%H-%M-%S'),
                    }
                ]
            },
            ReturnValues="UPDATED_NEW"
        )

    def update_append_user_item_attribute(self, username, item_title,item_price):
        response = self.users_table.update_item(
            Key={
                'UserName': username
            },
            UpdateExpression="SET cartItems = list_append(cartItems, :i)",
            ExpressionAttributeValues={
                ':i': [
                    {
                        "Title" :item_title,
                        "Price": item_price,
                        #"URL" :item_URL
                    }
                ]
            },
            ReturnValues="UPDATED_NEW"
        )

    def get_user_by_id(self, in_id):
        try:
            response = self.users_table.scan(
                FilterExpression=Key('id').eq(int(in_id)),
                ProjectionExpression="UserName, Password, id, Email"
            )
            #print(response)
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            if 'Items' in response.keys():
                item = response['Items']
                if len(item)>0:
                    print("GetItem succeeded:")
                    user = User()
                    user.id = item[0]['id']
                    user.username = item[0]['UserName']
                    user.encrypted_pass = item[0]['Password']
                    user.email = item[0].get('Email', '')
                    return user
                else:
                    return None
            else:
                return None

    def get_filename_by_barcode(self, username, barcode_value):
        fe = Key('UserName').eq(username) # & Key('BarcodesInfo.Barcode').eq(barcode_value)
        pe = "BarcodesInfo"
        try:
            response = self.users_table.query(
                KeyConditionExpression = "UserName = :u",
                FilterExpression = "BarcodesInfo.Barcode = :b",
                ProjectionExpression = pe,
                ExpressionAttributeValues = {
                    ":u" : username ,
                    ":b": barcode_value,
            }
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            if 'Items' in response.keys():
                item = response['Items']
                if len(item) > 0:
                    for it in item:
                        if barcode_value in it['Barcode']:
                            print("GetFileName succeeded:")
                            file_name = item[0]['StoredPhoto']
                            return file_name
                else:
                    return None
            else:
                return None

class EbaySDKManager():
    def __init__(self):
        try:
            self.finding_api = Finding(appid='GUANGZHE-ece1779a-PRD-7c62ba413-e3800b20', siteid='EBAY-ENCA', config_file=None)
        except ConnectionError as e:
            print(e)
            print(e.response.dict())

        try:
            self.shopping_api = Shopping(appid='GUANGZHE-ece1779a-PRD-7c62ba413-e3800b20', siteid='EBAY-ENCA', config_file=None)
        except ConnectionError as e:
            print(e)
            print(e.response.dict())

    def find_items_by_upc(self, upc):
        try:
            #example:'00717951008435'
            response = self.finding_api.execute('findItemsByProduct',
                                        {'productId': {'#text': upc, '@attrs': {'type': 'UPC'}}})
            response_dict = response.dict()
            items = []
            if 'searchResult' not in response_dict:
                return items
            top5items = response_dict['searchResult']['item'][:5]
            for i in top5items:
                ebayItem = EbayItem(i)
                items.append(ebayItem)
            return items
        except ConnectionError as e:
            print(e)
            print(e.response.dict())

    def find_items_by_id(self, id):
        try:
            #example:'00717951008435'
            response = self.finding_api.execute('findItemsByProduct',
                                        {'productId': {'#text': id, '@attrs': {'type': 'ePID'}}})
            response_dict = response.dict()
            items = []
            if 'searchResult' not in response_dict:
                print("no result for find item")
                return items
            top5items = response_dict['searchResult']['item'][:5]
            for i in top5items:
                ebayItem = EbayItem(i)
                items.append(ebayItem)
            return items
        except ConnectionError as e:
            print(e)
            print(e.response.dict())

    def find_items_by_keywords(self, keywords):
        try:
            #example: 'apples and oranges'
            response = self.finding_api.execute('findItemsAdvanced', {'keywords': keywords})
            response_dict = response.dict()
            items = []
            if 'searchResult' not in response_dict:
                return items
            top5items = response_dict['searchResult']['item'][:5]
            for i in top5items:
                ebayItem = EbayItem(i)
                items.append(ebayItem)
            return items
        except ConnectionError as e:
            print(e)
            print(e.response.dict())


class EbayItem():
    def __init__(self, item_dict):
        self.item_dict = item_dict
        self.itemId = item_dict.get('itemId', None)
        self.title = item_dict.get('title', None)
        # self.primaryCategory = item_dict.get('primaryCategory', None)
        # self.category = self.primaryCategory.get('categoryName', None) if self.primaryCategory is not None else None
        self.galleryURL = item_dict.get('galleryURL', None)
        self.viewItemURL = item_dict.get('viewItemURL', None)
        # self.postalCode = item_dict.get('postalCode', None)
        # self.location = item_dict.get('location', None)
        # self.country = item_dict.get('country', None)
        # self.shippingType = item_dict['shippingInfo'].get('shippingType', None)
        # self.shippingServiceCost = item_dict['shippingInfo'].get('shippingServiceCost', None)
        # self.shippingCost = self.shippingServiceCost['value'] if self.shippingServiceCost is not None else None
        # self.shipToLocations = item_dict['shippingInfo'].get('shipToLocations', None)
        self.price = item_dict['sellingStatus']['convertedCurrentPrice'].get('value', None)
        self.currency = item_dict['sellingStatus']['convertedCurrentPrice'].get('_currencyId', None)
        # self.condition = item_dict.get('condition', None).get('conditionDisplayName', None) \
        #     if item_dict.get('condition', None) is not None else None

class EtsySDKManager():
    def __init__(self):
        try:
            self.api_key = 'hjyvc5a4oz3dxhasc2nkc2ie'
        except Exception as e:
            print(e)

    def find_items_by_keywords(self, keywords):
        try:
            response = requests.get('https://openapi.etsy.com/v2/listings/active?api_key={}'
                                    '&limit=5&sort_on=score&keywords={}'
                                    .format(self.api_key, keywords))
            items = []
            if response.status_code != 200:
                return items

            dict = json.loads(response.text)

            results = dict.get('results', None)
            if results is None:
                return items

            if len(results) == 0:
                return items

            for item in results:
                etsyItem = EtsyItem(item)
                etsyItem.galleryURL = self.get_image_url_for_listing(etsyItem.itemId)
                items.append(etsyItem)

            return items
            # for i in top5items:
            #     ebayItem = EbayItem(i)
            #     items.append(ebayItem)
            # return items
        except Exception as e:
            print(e)

    def get_image_url_for_listing(self, listing_id):
        response = requests.get('https://openapi.etsy.com/v2/listings/:listing_id/images?api_key={}&listing_id={}'
                                .format(self.api_key, listing_id))
        url = ''
        if response.status_code != 200:
            return url

        dict = json.loads(response.text)

        results = dict.get('results', None)
        if results is None:
            return url

        if len(results) == 0:
            return url

        image = results[0]
        url = image['url_170x135']
        return url


class EtsyItem():
    def __init__(self, item_dict):
        # self.item_dict = item_dict
        self.itemId = str(item_dict['listing_id']) if item_dict.get('listing_id', None) is not None else ''
        self.title = item_dict.get('title', None)
        self.galleryURL = ''
        self.viewItemURL = item_dict.get('url', None)
        self.price = str(round(float(item_dict['price'])*1.33, ndigits=2))
        self.currency = 'CAD'

@login.user_loader
def load_user(id):
    print(id)
    dynamo = DynamoDBManager()
    user = dynamo.get_user_by_id(id)
    return user


