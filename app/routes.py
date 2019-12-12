from flask import render_template, flash, redirect, url_for, request, Response
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from app.forms import LoginForm, RegisterForm, UploadForm, BrowseForm, CartForm
from app import app
from app.models import DynamoDBManager, User, EbaySDKManager, EtsySDKManager, EmailManager
import app.secure as secure
import uuid
from datetime import datetime
import cv2
import numpy
from wand.image import Image
import os
import io
from pyzbar import pyzbar
import boto3
import urllib
from bs4 import BeautifulSoup
import random

from app.config import BUCKET_NAME

#globals

outputDomain = 'https://s3.amazonaws.com/' + BUCKET_NAME + '/'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

dynamo = DynamoDBManager()

@app.route('/')
@login_required
def home():
    data = dynamo.get_user_data(current_user.username)
    history = data['SearchHistory']
    return render_template('index.html', history=history)

@app.route('/index')
@login_required
def index():
    data = dynamo.get_user_data(current_user.username)
    history = data['SearchHistory']
    random.shuffle(history)
    return render_template('index.html', history=history)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_data = dynamo.get_user_data(form.username.data)
        if user_data is not None:
            if secure.verify_password(user_data['Password'], form.password.data):
                #creating user object
                user = User()
                user.encrypted_pass = user_data['Password']
                user.username = user_data['UserName']
                user.id = user_data['id']
                login_user(user, remember=True)
                flash('Login for user {} was successful.'.format(user_data['UserName']))
                return redirect(url_for('index'))
            else:
                flash('Username/password combination is not valid.')
        else:
            flash('No user with that username exists.')
    return render_template('login.html', title='Sign In', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if dynamo.get_user_data(form.username.data) is None:
            dynamo.register_new_user(form.username.data, secure.encrypt_password(form.password.data),
                                     uuid.uuid4().int >> 64, form.email.data)
            flash('Registration for user: {} was successful. Please login'.format(form.username.data))
            return redirect(url_for('login'))
        else:
            flash('Registration FAILED! User {} already exists.'.format(form.username.data))
            return redirect(url_for('register'))

    return render_template('register.html', title='Register', form=form)

# @app.route('/addtocart', methods=['GET', 'POST'])
# def addtocart():
#     itemId = request.form.get('itemId', None)
#     # ebay = EbaySDKManager()
#     # items = ebay.find_items_by_id(itemId)
#     # form = BrowseForm()
#     return redirect('browse')

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    form = BrowseForm()
    if form.validate_on_submit():
        if form.barcode.data.strip():
            ebay = EbaySDKManager()
            items = ebay.find_items_by_upc(form.barcode.data.strip())
            dict_items = [vars(x) for x in items]
            db = DynamoDBManager()
            db.update_append_user_search_history_attribute(current_user.username, "Barcode", form.barcode.data.strip(),
                                                           dict_items)
            if form.submit.data:
                html = render_template('browse.html', title='Browse', items=items, form=form, barcode=False)
                soup = BeautifulSoup(html)

                # kill all script and style elements
                for script in soup(["script", "style"]):
                    script.extract()  # rip it out

                # get text
                text = soup.get_text()

                # break into lines and remove leading and trailing space on each
                lines = (line.strip() for line in text.splitlines())
                # break multi-headlines into a line each
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                # drop blank lines
                text = '\n'.join(chunk for chunk in chunks if chunk)

                email = EmailManager()
                email.send_email(subject='SwiftShop: Here are your search results for Barcode '
                                         + form.barcode.data.strip(),
                                 sender=email.mail_settings['MAIL_USERNAME'],
                                 recipients=[current_user.email],
                                 html=render_template('browse.html', title='Browse', items=items, form=form, barcode=False),
                                 body=text)
                return render_template('browse.html', title='Browse', items=items, form=form, barcode=False)
        elif form.keyword.data.strip():
            ebay = EbaySDKManager()
            items = ebay.find_items_by_keywords(form.keyword.data.strip())
            etsy = EtsySDKManager()
            etsy_items = etsy.find_items_by_keywords(form.keyword.data.strip())
            items += etsy_items
            dict_items = [vars(x) for x in items]
            db = DynamoDBManager()
            db.update_append_user_search_history_attribute(current_user.username, "Keyword", form.keyword.data.strip(),
                                                           dict_items)
            if form.submit.data:
                email = EmailManager()

                html = render_template('browse.html', title='Browse', items=items, form=form, barcode=False)
                soup = BeautifulSoup(html)

                # kill all script and style elements
                for script in soup(["script", "style"]):
                    script.extract()  # rip it out

                # get text
                text = soup.get_text()

                # break into lines and remove leading and trailing space on each
                lines = (line.strip() for line in text.splitlines())
                # break multi-headlines into a line each
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                # drop blank lines
                text = '\n'.join(chunk for chunk in chunks if chunk)

                email.send_email(subject='SwiftShop: Here are your search results for Keywords "'
                                         + form.keyword.data.strip() + '"',
                                 sender=email.mail_settings['MAIL_USERNAME'],
                                 recipients=[current_user.email],
                                 html=render_template('browse.html', title='Browse', items=items, form=form,
                                                      barcode=False),
                                 body=text)
                return render_template('browse.html', title='Browse', items=items, form=form, barcode=False)
        # if form.addToCart.data:
        #     selecteditems = []
        #     for checkbox in ["checkbox"+str(i) for i in range(len(items))]:
        #         value = request.form.get(checkbox)
        #         if value:
        #             item = next((x for x in items if x['itemId'] == value), None)
        #             if item is not None:
        #                 selecteditems.append(item)
        #     render_template('cart.html', title='Cart', items=selecteditems, form=form)
    return render_template('browse.html', title='Browse', form=form, barcode=False)

@app.route('/cart', methods=['GET', 'POST'])
def cart():
     form = CartForm()
     if form.validate_on_submit():
         return render_template('cart.html', title='Cart', form=form)
     data = dynamo.get_user_data(current_user.username)
     cartItems = data['cartItems']
     # ebay = EbaySDKManager()
     # items = []
     sum = 0;
     for cartitem in cartItems:
         sum += float(cartitem['Price'])
     #    print("item:%s"%cartitem)
     #    items.append(ebay.find_items_by_keywords(cartitem))
     return render_template('cart.html', title='Cart', form=form, items = cartItems, sum = sum)

@app.route('/add_cart/<item_title>/<item_price>', methods=['GET', 'POST'])
def add_cart(item_title,item_price):
    dynamo.update_append_user_item_attribute(current_user.username, item_title,item_price)
    return redirect(url_for('index'))


@app.route('/barcode_browse/<barcode_code>/<fname>', methods=['GET', 'POST'])
def barcode_browse(barcode_code, fname):
    ebay = EbaySDKManager()
    items = ebay.find_items_by_upc(barcode_code)
    if len(items) == 0:
        form = UploadForm()
        flash('No information available for uploaded Barcode, please try again!')
        return render_template('upload_file.html', title='Upload Barcode', form=form)
    #S3_file_name= dynamo.get_filename_by_barcode(current_user.username,barcode_code)
    S3_file_name = fname
    return render_template('browse.html', title='Browse', items=items,  BUCKET=BUCKET_NAME, S3FileName=S3_file_name, barcode=True)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_file', methods=['GET', 'POST'])
@login_required
def upload_file():
    form = UploadForm()
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('Not a valid file')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        print("file name is %s" % file.filename)
        if file and allowed_file(file.filename):
            #detect barcode
            try:
                barcodes, fname = barcode_decoder(file)
                flash('Successfuly detected barcode')
                return redirect(url_for('barcode_browse',barcode_code = barcodes[0],fname = fname ))
            except Exception as e:
                flash('No barcode detected, please try again!')
                print(str(e))
    return render_template('upload_file.html', title='Upload Barcode', form=form)

def barcode_decoder(file):
    store_base = "B" + datetime.now().strftime('%Y-%m-%d-%H-%M-%S') + '-' + str(uuid.uuid4())
    store_ext = filename_extension(file.filename)
    const_file_name = store_base+ "_barcode" + "." + store_ext
    img = cv2.imdecode(numpy.fromstring(file.read(), numpy.uint8), cv2.IMREAD_UNCHANGED)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    barcodes = pyzbar.decode(gray)
    # loop over the detected barcodes
    barcodeData = []
    for barcode in barcodes:
        print("checking barcode")
        # extract the bounding box location of the barcode and draw the bounding box surrounding the barcode on the image
        (x, y, w, h) = barcode.rect
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 20)
        barcode_data = barcode.data.decode("utf-8")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, barcode_data, (x, y), font, 1.2, (0, 0, 0), 5, cv2.LINE_AA)
        # the barcode data is a bytes object so if we want to draw it on our output image we need to convert it to a string first
        barcodeData.append(barcode_data)
    #check if any barcode found
    if len(barcodeData) > 0:
        store_ext_dot = '.'+ store_ext
        r, outputImage = cv2.imencode(store_ext_dot, img)
        #storing in S3
        i_byte = io.BytesIO()
        i_byte.write(outputImage)
        i_byte.seek(0)
        #creating thumbnail
        with i_byte as new_file_b:
            img = Image(file=new_file_b)  # response
            i = img.clone()
            i.resize(240, 180)
        b_byte = io.BytesIO()
        i.save(file=b_byte)
        b_byte.seek(0)
        with b_byte as new_file_b:
            s3 = boto3.client('s3')
            s3.upload_fileobj(new_file_b, BUCKET_NAME, const_file_name, ExtraArgs={'ACL': 'public-read'})
        # print the barcode type and data to the terminal
        print("[INFO] Found barcode: {}".format(barcodeData))
        # store barcode data on dynamoDB [To Do]
        dynamo.update_append_user_barcode_attribute(current_user.username,barcodeData,const_file_name)
    else:
        raise Exception('Error encoding barcode')
    return barcodeData, const_file_name


def filename_extension(filename):
    _, file_extension = os.path.splitext(filename)
    return file_extension[1:]