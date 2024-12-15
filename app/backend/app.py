from flask import Flask, redirect, render_template, url_for, request
from pymongo import MongoClient

app = Flask(__name__)

client = MongoClient('mongodb://localhost:27017/')
db = client['scraper']
users_collection = db['users']

#api endpoints

#get is used to retrieve data from the server and not change anything
#post is used to send data to server. like submit a form or update.

#login
@app.route('/', methods=['GET', 'POST'])
def login():
    #if request.form == 'POST':
        #username = request.form['USERNAME']
        #password = request.form['PASSWORD']
    
    return render_template('login.html')

#register
@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')

#signout
@app.route('/signout', methods=['GET','POST'])
def signout():
    return render_template('signout.html')

#delete
@app.route('/delete', methods=['GET','POST'])
def delete():
    return render_template('delete.html')

#update password
@app.route('/update', methods=['GET','POST'])
def update():
    return render_template('update.html')

#home
@app.route('/home', methods=['GET','POST'])
def home():
    return render_template('home.html')

if __name__=="__main__":
    app.run(debug=True)

    