from flask import Flask, redirect, render_template, url_for, request, flash, session
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv#.env secret key, need for mongo but might change later.
from scraper import scrape_posts
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import pandas as pd
import numpy as np

load_dotenv()

#flask instance
app = Flask(__name__)

#random number key i stored in .env file.
app.secret_key = os.getenv('SECRET_KEY', 'some_default_secret')

#mongodb connection working on using postgre instead but this works.
client = MongoClient('mongodb://localhost:27017/proj')
mongo = client['proj']
collection = mongo['users']

TIME_FILTER_MAPPING = {
    'day': '5d',
    'week': '5d',
    'month': '1mo',
    'year': '1y',
    'all': 'max'
}

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
            #werkzeug password hash for user registration (security reasons) CHECK HASH.
            hashed_password = generate_password_hash(password)
            collection.insert_one({'username': username, 'password': hashed_password})
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))
    #return render_template('register.html') #get rid of this and the others later for react.
    return render_template('register.html')

#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    #set username and password from post.
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        #find user by username in db.
        user = collection.find_one({'username': username})
        if not user:
            flash('User does not exist.', 'danger')
            return redirect(url_for('login')) #stay on login
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
    if 'username' not in session:
        flash('You must be logged in to access this page.', 'danger')
        #REDIRECT TO LOGIN
        return redirect(url_for('login'))
    
    posts_data = []
    metrics = {}
    overall_sentiment_label = None
    plot = None
    total_posts = 0
    timeframe_description = ""

    #To store overall sentiment
    #To store summary if enabled
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

                post_counts_by_month = defaultdict(int)
                for post in posts_data:
                    post_date = post.get('date')
                    if post_date:
                        month = post_date.strftime('%Y-%m')
                        post_counts_by_month[month] += 1

                today = datetime.today()
                months = [(today - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(11, -1, -1)]

                stock_df = yf.download(stock, period='1y', interval='1mo', progress=False)
                if not stock_df.empty:
                    stock_df = stock_df.reset_index()
                    stock_df['Month'] = stock_df['Date'].dt.strftime('%Y-%m')
                    close_price_by_month = stock_df.set_index('Month')['Close'].to_dict()
                    avg_volume_by_month = stock_df.groupby('Month')['Volume'].mean().to_dict()
                    post_counts = [post_counts_by_month.get(month, 0) for month in months]
                    avg_volumes = [avg_volume_by_month.get(month, 0) / 10000 for month in months]
                    close_prices = [close_price_by_month.get(month, np.nan) for month in months]
                    for i in range(len(close_prices)):
                        if np.isnan(close_prices[i]):
                            if i > 0:
                                close_prices[i] = close_prices[i-1]
                            else:
                                close_prices[i] = 0
                else:
                    post_counts = [0] * 12
                    avg_volumes = [0] * 12
                    close_prices = [0] * 12

                fig, ax = plt.subplots(figsize=(10, 5))
                ax.set_title('Empty Plot')
                plt.savefig('static/plot.png')
                plt.close()
                plot = 'plot.png'
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
    #redirect to login after signout
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

#DELETE ACCOUNT
@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if 'username' not in session:
        flash('You must be logged in to delete your account.', 'danger')
        #redirect to login
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        #find user via username on db.
        user = collection.find_one({'username': username})
        #is password right?
        if user and check_password_hash(user['password'], password):
            #delete user from mongodb db.
            collection.delete_one({'username': username})
            session.pop('username', None)
            flash('Account deleted successfully.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('delete.html')

#UPDATE PASS
@app.route('/update', methods=['GET', 'POST'])
def update():
    if 'username' not in session:
        flash('You must be logged in to update your password.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        username = session['username']
        user = collection.find_one({'username': username})
        if user and check_password_hash(user['password'], old_password):
            if new_password == confirm_password:
                hashed_password = generate_password_hash(new_password)
                collection.update_one({'username': username}, {'$set': {'password': hashed_password}})
                flash('Password updated!', 'success')
                return redirect(url_for('home'))
            else:
                flash('New passwords do not match.', 'danger')
        else:
            flash('Wrong old password.', 'danger')
    return render_template('update.html')

if __name__ == "__main__":
    app.run(debug=True)
