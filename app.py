# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
# Note: Pillow is still used, but pillow-heif is no longer needed.
from PIL import Image

# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_change_me'

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'recipes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# We no longer need to check for HEIC here, as it will be converted by the browser
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

# --- Database Models ---
class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    prep_time = db.Column(db.String(50), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Recipe {self.title}>'

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---
@app.route('/')
def index():
    recipes = Recipe.query.order_by(Recipe.title).all()
    categorized_recipes = {
        'Appetizers': [r for r in recipes if r.category == 'Appetizer'],
        'Mains': [r for r in recipes if r.category == 'Main'],
        'Desserts': [r for r in recipes if r.category == 'Dessert'],
        'Drinks': [r for r in recipes if r.category == 'Drink']
    }
    return render_template('index.html', recipes=categorized_recipes)

@app.route('/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    recipe = db.get_or_404(Recipe, recipe_id)
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/recipe/add', methods=['GET', 'POST'])
def add_recipe():
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
            # The file is now converted to jpg by the browser if it was HEIC
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
            notes=notes, image_filename=image_filename
        )
        db.session.add(new_recipe)
        db.session.commit()
        
        flash(f'Recipe "{title}" added successfully!', 'success')
        return redirect(url_for('index'))
        
    return render_template('recipe_form.html', form_action='Add Recipe', recipe=None)

@app.route('/recipe/edit/<int:recipe_id>', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    recipe = db.get_or_404(Recipe, recipe_id)
    
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
            else:
                flash('Invalid image file type.', 'danger')
                return render_template('recipe_form.html', form_action='Edit Recipe', recipe=recipe)

        db.session.commit()
        flash(f'Recipe "{recipe.title}" updated successfully!', 'success')
        return redirect(url_for('view_recipe', recipe_id=recipe.id))

    return render_template('recipe_form.html', form_action='Edit Recipe', recipe=recipe)

@app.route('/recipe/delete/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    recipe = db.get_or_404(Recipe, recipe_id)
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
    app.run(debug=True)