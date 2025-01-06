from flask import Flask, redirect, render_template, url_for, request, flash, session 
import os
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import pandas as pd
import psycopg2 #for postgre
from psycopg2 import sql


from scraper import scrape_posts, is_valid_ticker 
from priceplot import generate_post_counts_stock_plot
from volumeplot import generate_post_counts_volume_plot

#TODO FIX: NotOpenSSLWarning - urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020 wtf
#postgre only configured for local.

#CONNECTION TO DATABASE: psql -h localhost -d scraper -U muhammadali636

load_dotenv() #load .env stuff
app = Flask(__name__)
app.secret_key = os.getenv("hidden_from_this_world") #aka  --------> the secret key for sessions. Key is required for flask sessions. 

#database stuff.
database_password = os.getenv('password')  
database_user = os.getenv('user')              
the_database = os.getenv('database')           
the_host = os.getenv('host')                  

def get_db_connection():
    connection = psycopg2.connect(
        host=the_host,
        database=the_database,
        user=database_user,
        password=database_password
    )
    return connection

#time filter mapping
TIME_FILTER_MAPPING = {'day': '1d','week': '5d','month': '1mo', 'year': '1y',  'all': 'max'}

#REG
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        #set the username and password from the form.
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        with get_db_connection() as connection:
            with connection.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))   #cheecks if user already exists
                user_exists = cur.fetchone()
                if user_exists:
                    flash('Username already exists. Please try again.', 'danger')
                else:
                    #werkzeug password hash for user registration (security reasons) CHECK HASH.
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256') # Insert new user. do not remove hash method or --> warning. 
                    cur.execute(
                        "INSERT INTO users (username, password) VALUES (%s, %s)",
                        (username, hashed_password)
                    )
                    connection.commit()
                    flash('Registration successful!', 'success')
                    #REDIRECT TO LOGIN
                    return redirect(url_for('login'))
    return render_template('register.html')

#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #set username and password from post.
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        with get_db_connection() as connection:
            with connection.cursor() as cur:
                #find user by username in db.
                cur.execute("SELECT username, password FROM users WHERE username = %s", (username,))
                result = cur.fetchone()
                if not result:
                    flash('User does not exist.', 'danger')
                    #stay on login
                    return redirect(url_for('login'))
                db_username, db_hashed_password = result
                if check_password_hash(db_hashed_password, password):
                    session['username'] = db_username                    #store username in session
                    flash('Logged in successfully!', 'success')
                    return redirect(url_for('home'))    #REDIRECT TO HOME
                else:                    #Wrong password
                    flash('Wrong password.', 'danger')
    return render_template('login.html')

#DELETE ACCOUNT
@app.route('/delete', methods=['GET', 'POST'])
def delete():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to delete your account!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        #find user via username on db.
        username_form = request.form['username'].strip()
        password_form = request.form['password'].strip()
        current_session_user = session['username']
        if username_form != current_session_user:      #make sure they are logging in before deleting.
            flash('The username does not match the logged-in account.', 'danger') 
            return render_template('delete.html')

        with get_db_connection() as connection:
            with connection.cursor() as cur:
                #check if user (from session) actually exists
                cur.execute("SELECT password FROM users WHERE username = %s", (current_session_user,))
                result = cur.fetchone()

                if not result:
                    flash('User does not exist.', 'danger')
                    return redirect(url_for('login'))

                db_hashed_password = result[0]
                if check_password_hash(db_hashed_password, password_form):
                    #delete user from database.
                    cur.execute("DELETE FROM users WHERE username = %s", (current_session_user,))
                    connection.commit()

                    #log out the user
                    session.pop('username', None)
                    flash('Account deleted successfully, sorry to see you go :(', 'success')
                    #REDIRECT TO LOGIN
                    return redirect(url_for('login'))
                else:
                    flash('Invalid username or password.', 'danger')

    return render_template('delete.html')

#UPDATE PASSWORD
@app.route('/update', methods=['GET', 'POST'])
def update():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to update your password.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        old_password = request.form['old_password'].strip()
        new_password = request.form['new_password'].strip()
        confirm_password = request.form['confirm_password'].strip()
        username = session['username']

        with get_db_connection() as connection:
            with connection.cursor() as cur:
                # heck if user exists ELSE redirect
                cur.execute("SELECT password FROM users WHERE username = %s", (username,))
                result = cur.fetchone()

                if not result:
                    flash('User does not exist.', 'danger')
                    return redirect(url_for('update'))

                db_hashed_password = result[0]

                # Check if the old password is correct
                if check_password_hash(db_hashed_password, old_password):
                    # Update the password if confirmation matches
                    if new_password == confirm_password:
                        hashed_new_password = generate_password_hash(new_password, method='pbkdf2:sha256')
                        cur.execute(
                            "UPDATE users SET password = %s WHERE username = %s",
                            (hashed_new_password, username)
                        )
                        connection.commit()
                        flash('Password updated!', 'success')
                        #return to home page on success
                        return redirect(url_for('home'))
                    else:
                        flash('New passwords do not match.', 'danger')
                else:
                    flash('Wrong old password.', 'danger')

    return render_template('update.html')

#SIGNOUT AND CLEAR SESSION
@app.route('/signout')
def signout():
    #pop username from sesh to logout.
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    #redirect to login after signout
    return redirect(url_for('login'))

@app.route('/home', methods=['GET', 'POST'])
def home():
    #REDIRECT TO LOGIN
    if 'username' not in session:
        flash('You must be logged in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    stock = None
    posts_data = []
    metrics = {}
    overall_sentiment_label = None
    plot_prices = None
    plot_volume = None
    total_posts = 0
    timeframe_description = ""

    if request.method == 'POST':
        stock = request.form.get('stock', '').strip().upper()
        time_filter = request.form.get('time_filter', '').strip().lower()
        selected_subreddits = request.form.getlist('subreddits') 

        if not selected_subreddits:
            flash('Please select at least one subreddit.', 'warning')
        elif not stock:
            flash('Please enter a stock symbol.', 'warning')
        else:
            # MUST CHECK if ticker is valid FIRST IF NOT flash else flash
            if not is_valid_ticker(stock):
                flash('Ticker not found.', 'warning')
            else:
                period = TIME_FILTER_MAPPING.get(time_filter, '1mo')

                #1) SCRAPE (user-chosen timeframe) for the main results
                try:
                    posts_data, metrics, overall_sentiment_label = scrape_posts(stock, time_filter, selected_subreddits, period)
                except Exception as e:
                    flash(f'ERROR while scraping posts: {e}', 'danger')
                    posts_data, metrics, overall_sentiment_label = [], {}, None

                if not posts_data and not metrics:
                    flash('No valid posts found or invalid inputs.', 'warning')
                else:
                    total_posts = len(posts_data)

                #textual label for the timeframe
                if period == '1mo':
                    timeframe_description = "1 Month"
                elif period == '1d':
                    timeframe_description = "1 Day"
                elif period == '5d':
                    timeframe_description = "5 Days"
                elif period == '1y':
                    timeframe_description = "1 Year"
                else:
                    timeframe_description = "All Time"

                # ALWAYS GET 1 YEAR WORTH OF POSTS FOR PLOTS ignores the user inputted time_filter
                try:
                    plot_posts_data, _, _ = scrape_posts(stock, time_filter='year',  subreddits=selected_subreddits, period='1y')
                except Exception as e:
                    flash(f'ERROR while scraping data for the 12-month plot: {e}', 'danger')
                    plot_posts_data = []

                #gen plots
                if plot_posts_data:
                    try:
                        plot_prices = generate_post_counts_stock_plot(plot_posts_data, stock) 
                    except Exception as e:
                        flash(f'ERROR while generating the stock plot: {e}', 'danger')
                        plot_prices = None

                    try:
                        plot_volume = generate_post_counts_volume_plot(plot_posts_data, stock)
                    except Exception as e:
                        flash(f'ERROR while generating the volume plot: {e}', 'danger')
                        plot_volume = None

    return render_template(
        'home.html',
        stock=stock,
        posts_data=posts_data,
        metrics=metrics,
        overall_label=overall_sentiment_label,
        plot_prices=plot_prices,
        plot_volume=plot_volume,
        total_posts=total_posts,
        timeframe_description=timeframe_description if timeframe_description else ""
    )


if __name__ == "__main__":
    app.run(debug=True)
