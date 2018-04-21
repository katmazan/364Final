import os
import json
import datetime

from flask import Flask, url_for, redirect, render_template, session, request, flash
from flask_sqlalchemy import SQLAlchemy
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError, RadioField
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_login import LoginManager, login_required, login_user, logout_user, current_user, UserMixin
from requests_oauthlib import OAuth2Session
from requests.exceptions import HTTPError
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import praw
import settings
import json


####App Setup###
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'thisisastring'



app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/SI364projectplankatmazan"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

reddit = praw.Reddit(client_id=settings.red_client,
                     client_secret= settings.red_secret,
                     user_agent='User Agent:script:python.my.data.collection:v1.2.3 (by /u/katarain)')

potential_subs = db.Table('potential_subs' , db.Column('sub_id', db.Integer, db.ForeignKey('subs.id')), db.Column('reclist_id', db.Integer, db.ForeignKey('sublists.id')))
##Models##
##users will have one to many relationship with subreddit lists
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    recommendations = db.relationship('RecommendationList',backref='User')
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

class Subreddit(db.Model):
    __tablename__ = "subs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    favorite = db.Column(db.String(1))
##many-to-many with subreddits a recommendation list containts many subreddits and one subreddit could be in many different lists
class RecommendationList(db.Model):
    __tablename__ = 'sublists'
    id = db.Column(db.Integer, primary_key = True)
    subs = db.relationship('Subreddit', secondary = potential_subs, backref = db.backref('sublists', lazy = 'dynamic'), lazy = 'dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    searched_topic = db.Column(db.String, db.ForeignKey('searches.term'))

class SearchedTopics(db.Model):
    __tablename__ = 'searches'
    id = db.Column(db.Integer, primary_key = True)
    term = db.Column(db.String(50), unique = True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
class TopPots(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String)

##FORMS##
class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

# Provided
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

class SubSearchForm(FlaskForm):
    search = StringField("Enter a term to search Subreddits", validators=[Required()])
    submit = SubmitField('Submit')
    def validate_search(self, field):
        if " " in field.data:
            raise ValidationError('Subreddit searches may not have spaces')

class FavoriteForm(FlaskForm):
    sub_picks = SelectMultipleField('Choose Subreddits')
    fav = RadioField('Select * to favorite', choices = [('-', 'not fav'), ('fav','*')])
    submit = SubmitField()

class UpdateFavForm(FlaskForm):
    newdata = RadioField('Select * to favorite', choices = [('-', 'not fav'), ('fav','*')])
    submit = SubmitField('Update')

class DeleteButtonForm(FlaskForm):
    submit = SubmitField('Delete')
##Helper Functions##
def get_subs_from_reddit(topic):
    sub_list = []
    blah = reddit.subreddits.search_by_topic(topic)
    for thing in blah:
        sub_title = str(thing.display_name)
        
        sub_list.append(sub_title)
    return sub_list
def get_posts_from_sub(sub):
    post_list = []
    red = reddit.subreddit(sub).hot(limit=5)
    for thing in red:
        post_list.append(thing)
    return post_list
def get_or_create_sub(db_session,title, favorite):
    
    print(title)
    
    s = Subreddit.query.filter_by(title=title).first()
    print('hi')
    if s:
        return s
    else:
        s = Subreddit(title=title, favorite = favorite)
        
            
        db_session.add(s)
        db_session.commit()
        return s
def get_or_create_search_term(db_session, term, current_user):
    sub_list = []
    try_term = SearchedTopics.query.filter_by(term = term, user_id = current_user).first()
    print(term)
    if try_term:
        return try_term
    else:
        ##print('hello')
        new_term = SearchedTopics(term=term, user_id = current_user)
        print(new_term)
        data = get_subs_from_reddit(term)
        print(data)
        
        for sub in data:
            add_sub = get_or_create_sub(db.session, title = sub, favorite = '')
            sub_list.append(add_sub)
           
        db_session.add(new_term)
        db_session.commit()
        get_or_create_list(db.session,current_user, term, sub_list)
        return new_term

def get_or_create_list(db_session, current_user, searched_topic , subs_list = []):
    
   
    sub_list = RecommendationList.query.filter_by(user_id = current_user, searched_topic = searched_topic).first()
    ##subs_list = get_subs_from_reddit(searched_topic)
    
    if sub_list:
        return sub_list
    else:
        sub_list = RecommendationList(searched_topic = searched_topic, user_id = current_user, subs = [])
        for sub in subs_list:
            ## Don't have song artist, album and genre information. So passing those as empty parameters
            ##print(type(sub.title))

            s = get_or_create_sub(db.session, title = sub.title, favorite = '')
            ## Appending each returned song to the relationship property of playlist object
            sub_list.subs.append(s)
        sub_list = RecommendationList(searched_topic = searched_topic, user_id = current_user, subs = subs_list)
        db_session.add(sub_list)
        db_session.commit()
        return sub_list
def get_or_create_post(db_session, title):
    
    post = TopPots.query.filter_by(title=title).first()
    if post:
        return post
    else:
        post = TopPots(title=title)
        
            
        db_session.add(post)
        db_session.commit()
        return post
##ROUTES##

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500



@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    return render_template('register.html',form=form)

@app.route('/secret')
@login_required
def secret():
    return "Only authenticated users can do this! Try to log in or contact the site admin."

##this will use a form to search for subreddits based on topic, will save the search and redirect to a page that shows suggested subreddits which will also be saved in teh db as a recommendation list
@app.route('/', methods = ['GET', 'POST'])
@login_required
def index():
    form = SubSearchForm()
   
    search = form.search.data
    if form.validate_on_submit():
        
        get_or_create_search_term(db.session, term = search, current_user = current_user.id)
        print(search)
        return redirect(url_for('search_topics', search_term = search))
    errors = [v for v in form.errors.values()]
    if len(errors) > 0:
        flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
    return render_template('index.html',form=form)

##will return a list of topics searched, linking out to the recommendation lists if a topic is chosen
@app.route('/topics_searched')
@login_required
def search_topics():
    topics = SearchedTopics.query.all()
    print(topics)
    ##topics = term.all()
    return render_template('search_topics.html',topics=topics)

##will render a form that has a drop down menu of choices of subreddits saved, when chosen will redirect to a pgae of the top 5 post titles, which will be saved in the Posts db
@app.route('/top_posts/<sub_id>')
def hot_posts(sub_id):
    form = DeleteButtonForm()
    post_list = []
    posts = get_posts_from_sub(sub_id)
    for post in posts:
        print(post.id)
       
        post_list.append(get_or_create_post(db.session, title = str(post.title)))
    return render_template('top_posts.html', posts = post_list, form = form)

##will show a lists of all recommendation lists which can be clicked to view the subreddits in that list on a different page
@app.route('/recommendations/<search_topic>')
@login_required
def show_recommendations(search_topic):
    form = UpdateFavForm()
    searched_topic = str(search_topic)
    rec_list = RecommendationList.query.filter_by(searched_topic = search_topic).first()
    chosen = rec_list.subs.all()
    return render_template('recommendations.html', rec_list = chosen, form = form)
##will show all currently favorited subs
@app.route('/favsubs', methods = ['GET', "POST"])
def show_favs():
    form = FavoriteForm()
    subs = Subreddit.query.all()
    choices = [(str(s.id), s.title) for s in subs]
    form.sub_picks.choices = choices

    return render_template('favorite_subs.html', form = form)
##will update the status of a subreddit as favorite or not favorite wil flash a message and return to list of favsubs
@app.route('/update/<item>',methods=["GET","POST"])
def update(item):
    form = UpdateFavForm()
    if form.validate_on_submit():
        newdata = form.newdata.data
        p = RecommendationList.query.filter_by(id = item).first()
        p.favorite = newdata
        db.session.commit()
        flash("Updated priority of " + p.searched_topic)
        return redirect(url_for('index'))
    return render_template('update_item.html',item_name = item, form = form)
##will delete a recommendation list and return to home
@app.route('/delete/<item>',methods=["GET","POST"])
def delete(item):
    form = DeleteButtonForm()
    if form.validate_on_submit():
        s = TopPots.query.filter_by(id = item).first()
        db.session.delete(s)
        db.session.commit()
        flash("Deleted Post " + s.title)
        return redirect(url_for('index'))
    return render_template('recommendations.html', form = form)
if __name__ == "__main__":
    db.create_all()
    manager.run()
