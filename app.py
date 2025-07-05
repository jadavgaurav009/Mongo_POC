# app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime  # Make sure this is imported
import os

app = Flask(__name__)
app.secret_key = 'your_super_secret_key'  # Keep this for flash messages


# --- NEW ADDITION/UPDATE START ---
# Context processor to make 'now' (current datetime) available in all templates
@app.context_processor
def inject_global_data():
    return dict(now=datetime.now())


# --- NEW ADDITION/UPDATE END ---

# MongoDB Connection
try:
    client = MongoClient('mongodb://localhost:27017/')  # Replace with your MongoDB URI
    db = client.product_db  # Your database name
    products_collection = db.products  # Your collection name
    print("MongoDB connected successfully!")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    # Exit or handle the error appropriately in a real application

# Configuration for image uploads (Optional, but good for POC)
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Routes ---

@app.route('/')
def index():
    # Redirect to product list
    return redirect(url_for('list_products'))


@app.route('/products')
@app.route('/products/<int:page>')
def list_products(page=1):
    products_per_page = 10
    skip_amount = (page - 1) * products_per_page

    total_products = products_collection.count_documents({})
    products = products_collection.find().skip(skip_amount).limit(products_per_page)

    total_pages = (total_products + products_per_page - 1) // products_per_page

    return render_template('product_list.html',
                           products=products,
                           current_page=page,
                           total_pages=total_pages,
                           total_products=total_products)


@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        # You might want to generate product_id here if it's not user-input
        product_id = request.form['product_id']
        product_code = request.form['product_code']
        product_name = request.form['product_name']
        product_description = request.form['product_description']

        product_effective_date_str = request.form['product_effective_date']
        product_expiry_date_str = request.form['product_expiry_date']

        # Basic Validation
        if not all([product_id, product_code, product_name, product_description, product_effective_date_str,
                    product_expiry_date_str]):
            flash('All fields are required!', 'danger')
            # Pass the product data back to the form if validation fails
            # This allows user to see their input again
            return render_template('product_form.html', product=request.form)

            # Date Validation and Conversion
        try:
            product_effective_date = datetime.strptime(product_effective_date_str, '%Y-%m-%d')
            product_expiry_date = datetime.strptime(product_expiry_date_str, '%Y-%m-%d')
            if product_effective_date > product_expiry_date:
                flash('Effective date cannot be after expiry date!', 'danger')
                return render_template('product_form.html', product=request.form)
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return render_template('product_form.html', product=request.form)

        product_image_path = ''
        if 'product_image' in request.files:
            file = request.files['product_image']
            if file and allowed_file(file.filename):
                filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filename)
                product_image_path = f"/static/images/{file.filename}"
            else:
                flash('Invalid image file type. Allowed: png, jpg, jpeg, gif', 'warning')
                # You might want to proceed without an image or require it

        new_product = {
            "product_id": product_id,
            "product_code": product_code,
            "product_name": product_name,
            "product_description": product_description,
            "product_image_path": product_image_path,
            "product_insert_date": datetime.now(),
            "product_effective_date": product_effective_date,
            "product_expiry_date": product_expiry_date,
            "product_update_date": datetime.now(),
            "is_active": True
        }

        try:
            products_collection.insert_one(new_product)
            flash('Product added successfully!', 'success')
            return redirect(url_for('list_products'))
        except Exception as e:
            flash(f'Error adding product: {e}', 'danger')

    # For GET request, render empty form (product is None)
    return render_template('product_form.html', product=None)


@app.route('/product/edit/<product_id_str>', methods=['GET', 'POST'])
def edit_product(product_id_str):
    try:
        product_oid = ObjectId(product_id_str)
        product = products_collection.find_one({"_id": product_oid})
    except Exception:
        flash('Product not found!', 'danger')
        return redirect(url_for('list_products'))

    if not product:
        flash('Product not found!', 'danger')
        return redirect(url_for('list_products'))

    if request.method == 'POST':
        # Update product data from form, keeping original _id, product_id, insert_date
        product['product_code'] = request.form['product_code']
        product['product_name'] = request.form['product_name']
        product['product_description'] = request.form['product_description']

        product_effective_date_str = request.form['product_effective_date']
        product_expiry_date_str = request.form['product_expiry_date']

        # Basic Validation for POST during edit
        if not all([product['product_code'], product['product_name'], product['product_description'],
                    product_effective_date_str, product_expiry_date_str]):
            flash('All fields are required!', 'danger')
            # Pass the current product (with updated form data) back to the form
            # To re-populate fields
            product.update(request.form)  # Update product dict with submitted form data
            return render_template('product_form.html', product=product)

        # Date Validation and Conversion
        try:
            product['product_effective_date'] = datetime.strptime(product_effective_date_str, '%Y-%m-%d')
            product['product_expiry_date'] = datetime.strptime(product_expiry_date_str, '%Y-%m-%d')
            if product['product_effective_date'] > product['product_expiry_date']:
                flash('Effective date cannot be after expiry date!', 'danger')
                product.update(request.form)
                return render_template('product_form.html', product=product)
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            product.update(request.form)
            return render_template('product_form.html', product=product)

        if 'product_image' in request.files:
            file = request.files['product_image']
            if file and allowed_file(file.filename):
                filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filename)
                product['product_image_path'] = f"/static/images/{file.filename}"
            elif file.filename != '':  # If a file was selected but not allowed
                flash('Invalid image file type. Allowed: png, jpg, jpeg, gif', 'warning')

        product['product_update_date'] = datetime.now()

        try:
            # We use $set to update only the modified fields, not overwrite the whole doc
            # This is safer, especially for fields like _id, product_id, insert_date
            products_collection.update_one({"_id": product_oid}, {"$set": {
                "product_code": product['product_code'],
                "product_name": product['product_name'],
                "product_description": product['product_description'],
                "product_image_path": product['product_image_path'],
                "product_effective_date": product['product_effective_date'],
                "product_expiry_date": product['product_expiry_date'],
                "product_update_date": product['product_update_date'],
                "is_active": product.get('is_active', True)  # Keep existing or default to True
            }})
            flash('Product updated successfully!', 'success')
            return redirect(url_for('list_products'))
        except Exception as e:
            flash(f'Error updating product: {e}', 'danger')

    # For GET request (to display edit form)
    return render_template('product_form.html', product=product)


@app.route('/product/delete/<product_id_str>', methods=['POST'])
def delete_product(product_id_str):
    try:
        product_oid = ObjectId(product_id_str)
        result = products_collection.delete_one({"_id": product_oid})
        if result.deleted_count == 1:
            flash('Product deleted successfully!', 'success')
        else:
            flash('Product not found!', 'danger')
    except Exception as e:
        flash(f'Error deleting product: {e}', 'danger')
    return redirect(url_for('list_products'))


@app.route('/product/detail/<product_id_str>')
def product_detail(product_id_str):
    try:
        product_oid = ObjectId(product_id_str)
        product = products_collection.find_one({"_id": product_oid})
    except Exception:
        flash('Product not found!', 'danger')
        return redirect(url_for('list_products'))

    if not product:
        flash('Product not found!', 'danger')
        return redirect(url_for('list_products'))

    return render_template('product_detail.html', product=product)


if __name__ == '__main__':
    # Create the upload folder if it doesn't exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)  # Set debug=False in production