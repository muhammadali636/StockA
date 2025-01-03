from flask import Flask, redirect, render_template, url_for, request, flash, session
from pymongo import MongoClient
import os
from werkzeug.security import generate_password_hash, check_password_hash #password hashing
from dotenv import load_dotenv #.env secret key

#current just user auth, sessions, logging. 
#TODO: fix up scraper. its bad.

app = Flask(__name__) #flask instance

app.secret_key = os.getenv('SECRET_KEY') #random number key i stored in .env file. 

#mongodb connection working on using postgre instead but this works.
client = MongoClient('mongodb://localhost:27017/proj')
mongo = client['proj']
collection = mongo['users']

#REGISTRATION
@app.route('/', methods=['GET', 'POST'])
def register():
    #set the username and password from the form.
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        #check if user exists.
        if collection.find_one({'username': username}):
            flash('Username already exists. Please try again.', 'danger')
        else:
            #werkzeug password hash for user registration (secure)
            hashed_password = generate_password_hash(password)
            collection.insert_one({'username': username, 'password': hashed_password})
            flash('Registration successful. You can now login.', 'success')
            return redirect(url_for('login')) 

    return render_template('register.html') #get rid of this and the others later for react.

#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    #set username and password from post. 
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = collection.find_one({'username': username})       #find user by username in db.

        if user is None:
            flash('Username doesnt exist', 'danger')
            return redirect(url_for('login'))  #stay on login

        #check if the password
        if check_password_hash(user['password'], password):
            flash('Login successful.', 'success')
            #store username in session 
            session['username'] = username
            return redirect(url_for('home'))  #REDIRECT TO HOME
        else:
            flash('Wrong password.', 'danger')  #Wrong password

    return render_template('login.html')

#Home route (authentication check)
@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'username' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('login'))  #REDIRECT TO LOGIN
    return render_template('home.html')


@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'username' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('login'))

    posts_data = []
    metrics = {}
    overall_sentiment_label = None  # To store overall sentiment
    summary = ""  # To store summary if enabled

    if request.method == 'POST':
        #get form data
        stock = request.form.get('stock', '').strip().upper()
        time_filter = request.form.get('time_filter', '').strip().lower()
        selected_subreddits = request.form.getlist('subreddits')

        if not selected_subreddits:
            flash('Please select at least one subreddit.', 'warning')
        elif not stock:
            flash('Please enter a stock symbol.', 'warning')
        else:
            #call scrape_posts with the provided data

            #posts_data, metrics, overall_sentiment_label, summary = scrape_posts(
            #   stock, time_filter, selected_subreddits
            #)
            posts_data, metrics, overall_sentiment_label = scrape_posts(
                stock, time_filter, selected_subreddits
            )
            #summarize openai, you can call it here:
            #summary = summarize_posts(posts_data, stock)

            #nno posts or metrics found flash warning
            if not posts_data and not metrics:
                flash('No valid posts found or invalid inputs.', 'warning')
    return render_template('home.html',
                           posts_data=posts_data,
                           metrics=metrics,
                           overall_label=overall_sentiment_label,
                           summary=summary) 

#SIGNOUT AND CLEAR SESSION
@app.route('/signout', methods=['GET', 'POST'])
def signout():
    session.pop('username', None)  #pop username from sesh to logout.
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))  #redirect to login after signout

#DELETE ACCOUNT
@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if 'username' not in session:
        flash('You must be logged in to delete your account.', 'danger')
        return redirect(url_for('login'))  #redirect to login

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        #find user via username on db.
        user = collection.find_one({'username': username})

        if user and check_password_hash(user['password'], password):  #is password right?
            #delete user from mongodb db
            result = collection.delete_one({'username': username})
            print(f"Deleted {result.deleted_count} user(s)")

            #CLEAR SESSION AND LOGOUT (POP USER)
            session.pop('username', None)  #logout
            flash('Your account has been deleted successfully.', 'success')
            return redirect(url_for('login'))  #redirect to login
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('delete.html')

#UPDATE PASSWORD, VALIDATE USERNAME, CHECK OLD PASSWORD, UPDATE NEW PASSWORD
@app.route('/update', methods=['GET', 'POST'])
def update():
    if 'username' not in session:
        flash('You must be logged in to update your password.', 'danger')
        return redirect(url_for('login'))  #REDIRECT TO LOGIN

    if request.method == 'POST':
        username = session['username']
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        user = collection.find_one({'username': username}) #find user by username in db MONGO

        #validate old pass and new pass.
        if user and check_password_hash(user['password'], old_password):
            if new_password == confirm_password:
                #hash new pass.
                hashed_password = generate_password_hash(new_password)
                collection.update_one({'username': username}, {'$set': {'password': hashed_password}})
                flash('Password updated!', 'success')
                return redirect(url_for('home')) 
            else:
                flash('New passwords dont match. Please try again.', 'danger')
        else:
            flash('Wrong old password. Please try again.', 'danger')

    return render_template('update.html')


if __name__ == "__main__":
    app.run(debug=True)
