# app.py
import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from PIL import Image
from authlib.integrations.flask_client import OAuth

# --- Configuration ---
app = Flask(__name__)

# You can set a manual secret key for development
app.config['SECRET_KEY'] = 'a_default_dev_secret_key'

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'recipes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)
oauth = OAuth(app)

# --- Google OAuth Configuration ---
# Manual configuration: Replace placeholders with your actual credentials.
# WARNING: Do NOT use this method in a production environment.
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    # Let server_metadata_url discover the endpoints automatically
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# --- Database Models ---
class User(db.Model):
    """Represents a user in the database."""
    id = db.Column(db.String(100), primary_key=True) # Google's user ID
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    profile_pic = db.Column(db.String(200), nullable=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True, cascade="all, delete-orphan")

class Recipe(db.Model):
    """Represents a recipe, now linked to a user."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    prep_time = db.Column(db.String(50), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable=False)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Authentication Routes ---
@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = google.authorize_access_token()
    # The user info is parsed from the 'id_token' that is part of the token
    user_info = token['userinfo']

    # Check if user exists, if not, create one
    # 'sub' is the standard OpenID claim for subject (user) identifier
    user = User.query.get(user_info['sub']) 
    if not user:
        user = User(
            id=user_info['sub'], 
            name=user_info['name'], 
            email=user_info['email'], 
            profile_pic=user_info['picture']
        )
        db.session.add(user)
        db.session.commit()

    # Store a simplified user object in the session
    session['user'] = {
        'id': user.id,
        'name': user.name,
        'profile_pic': user.profile_pic
    }
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# --- Core Application Routes ---
@app.route('/')
def index():
    if 'user' not in session:
        return render_template('login.html')

    user_id = session['user']['id']
    recipes = Recipe.query.filter_by(user_id=user_id).order_by(Recipe.title).all()
    
    categorized_recipes = {
        'Appetizers': [r for r in recipes if r.category == 'Appetizer'],
        'Mains': [r for r in recipes if r.category == 'Main'],
        'Desserts': [r for r in recipes if r.category == 'Dessert'],
        'Drinks': [r for r in recipes if r.category == 'Drink']
    }
    return render_template('index.html', recipes=categorized_recipes)

@app.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    recipe = db.get_or_404(Recipe, recipe_id)
    
    # Authorization check
    if recipe.user_id != session['user']['id']:
        flash("You are not authorized to view this recipe.", "danger")
        return redirect(url_for('index'))
        
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/recipe/add', methods=['GET', 'POST'])
def add_recipe():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        prep_time = request.form['prep_time']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        notes = request.form['notes']
        
        image_file = request.files.get('image')
        image_filename = None

        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            if allowed_file(filename):
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                image_filename = filename
            else:
                flash('Invalid image file type.', 'danger')
                return render_template('recipe_form.html', form_action='Add Recipe', recipe=request.form)

        new_recipe = Recipe(
            title=title, category=category, prep_time=prep_time,
            ingredients=ingredients, instructions=instructions,
            notes=notes, image_filename=image_filename,
            user_id=session['user']['id'] # Link recipe to the logged-in user
        )
        db.session.add(new_recipe)
        db.session.commit()
        
        flash(f'Recipe "{title}" added successfully!', 'success')
        return redirect(url_for('index'))
        
    return render_template('recipe_form.html', form_action='Add Recipe', recipe=None)

@app.route('/recipe/edit/<int:recipe_id>', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    recipe = db.get_or_404(Recipe, recipe_id)

    # Authorization check
    if recipe.user_id != session['user']['id']:
        flash("You are not authorized to edit this recipe.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        recipe.title = request.form['title']
        recipe.category = request.form['category']
        recipe.prep_time = request.form['prep_time']
        recipe.ingredients = request.form['ingredients']
        recipe.instructions = request.form['instructions']
        recipe.notes = request.form['notes']
        
        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            if allowed_file(filename):
                if recipe.image_filename:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], recipe.image_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                recipe.image_filename = filename

        db.session.commit()
        flash(f'Recipe "{recipe.title}" updated successfully!', 'success')
        return redirect(url_for('view_recipe', recipe_id=recipe.id))

    return render_template('recipe_form.html', form_action='Edit Recipe', recipe=recipe)

@app.route('/recipe/delete/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    recipe = db.get_or_404(Recipe, recipe_id)
    
    # Authorization check
    if recipe.user_id != session['user']['id']:
        flash("You are not authorized to delete this recipe.", "danger")
        return redirect(url_for('index'))
    
    if recipe.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], recipe.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(recipe)
    db.session.commit()
    
    flash(f'Recipe "{recipe.title}" deleted successfully!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, ssl_context='adhoc')
