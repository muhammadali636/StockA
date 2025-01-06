from flask import Flask, redirect, render_template, url_for, request, flash, session
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from scraper import scrape_posts, generate_post_counts_stock_plot
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for headless environments
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import pandas as pd

#.env secret key, need for mongo but might change later.
load_dotenv()

#flask instance
app = Flask(__name__)
#random number key i stored in .env file.
app.secret_key = os.getenv('SECRET_KEY', 'some_default_secret')

client = MongoClient('mongodb://localhost:27017/proj') #mongodb connection WORKS but TODO: switch to postgre instead but this works.

mongo = client['proj']
collection = mongo['users']

#tme filter maps
TIME_FILTER_MAPPING = {
    'day': '5d',
    'week': '5d',
    'month': '1mo',
    'year': '1y',
    'all': 'max'
}

#REG
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        #set the username and password from the form.
        username = request.form['username'].strip()
        password = request.form['password']
        #check if user exists.
        if collection.find_one({'username': username}):
            flash('Username already exists. Please try again.', 'danger')
        else:
            #werkzeug password hash for user registration (security reasons) CHECK HASH.
            hashed_password = generate_password_hash(password)
            collection.insert_one({'username': username, 'password': hashed_password})
            flash('Registration successful!', 'success')
            #REDIRECT TO LOGIN
            return redirect(url_for('login'))
    #return render_template('register.html') #get rid of this and the others later for react.
    return render_template('register.html')

#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #set username and password from post.
        username = request.form['username'].strip()
        password = request.form['password']
        #find user by username in db.
        user = collection.find_one({'username': username})
        #stay on login
        if not user:
            flash('User does not exist.', 'danger')
            return redirect(url_for('login'))
        #check if the password
        if check_password_hash(user['password'], password):
            #store username in session
            session['username'] = username
            flash('Logged in successfully!', 'success')
            #REDIRECT TO HOME
            return redirect(url_for('home'))
        else:
            #Wrong password
            flash('Wrong password.', 'danger')
    return render_template('login.html')

#Home route (authentication check)
@app.route('/home', methods=['GET', 'POST'])
def home():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('login'))

    #To store overall sentiment
    posts_data = []
    metrics = {}
    overall_sentiment_label = None
    # store summary if enabled
    plot = None
    total_posts = 0
    timeframe_description = ""

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
            #validate time_filter
            period = TIME_FILTER_MAPPING.get(time_filter, '1mo')
            try:
                #call scrape_posts with the provided data
                posts_data, metrics, overall_sentiment_label = scrape_posts(stock, time_filter, selected_subreddits, period)
            except Exception as e:
                flash(f'An error occurred while scraping posts: {e}', 'danger')
                posts_data, metrics, overall_sentiment_label = [], {}, None
            #nno posts or metrics found flash warning
            if not posts_data and not metrics:
                flash('No valid posts found or invalid inputs.', 'warning')
            if metrics and posts_data:
                total_posts = len(posts_data)
                if period == '1mo':
                    timeframe_description = "1 Month"
                elif period == '5d':
                    timeframe_description = "5 Days"
                elif period == '1y':
                    timeframe_description = "1 Year"
                else:
                    timeframe_description = "All Time"
                try:
                    plot = generate_post_counts_stock_plot(posts_data, stock)
                except Exception as e:
                    flash(f'An error occurred while generating the plot: {e}', 'danger')
                    plot = None
    return render_template('home.html',
                           posts_data=posts_data,
                           metrics=metrics,
                           overall_label=overall_sentiment_label,
                           plot=plot,
                           total_posts=total_posts,
                           timeframe_description=timeframe_description if timeframe_description else "")

#SIGNOUT AND CLEAR SESSION
@app.route('/signout')
def signout():
    #pop username from sesh to logout.
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    #redirect to login after signout
    return redirect(url_for('login'))

#DELETE ACCOUNT
@app.route('/delete', methods=['GET', 'POST'])
def delete():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to delete your account.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        #find user via username on db.
        username = request.form['username'].strip()
        password = request.form['password']
        user = collection.find_one({'username': username})
        #is password right?
        if user and check_password_hash(user['password'], password):
            #delete user from mongodb db.
            collection.delete_one({'username': username})
            session.pop('username', None)
            flash('Account deleted successfully.', 'success')
            #REDIRECT TO LOGIN
            return redirect(url_for('login'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('delete.html')

#UPDATE PASS
@app.route('/update', methods=['GET', 'POST'])
def update():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to update your password.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        username = session['username']
        user = collection.find_one({'username': username})
        #check if the old password is correct
        if user and check_password_hash(user['password'], old_password):
            #update the password if confirmation matches
            if new_password == confirm_password:
                hashed_password = generate_password_hash(new_password)
                collection.update_one({'username': username}, {'$set': {'password': hashed_password}})
                flash('Password updated!', 'success')
                #return to home page on success
                return redirect(url_for('home'))
            else:
                flash('New passwords do not match.', 'danger')
        else:
            flash('Wrong old password.', 'danger')
    return render_template('update.html')

if __name__ == "__main__":
    # Ensure the 'static' directory exists
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)
