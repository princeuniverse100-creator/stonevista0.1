from flask import Flask, render_template, request, send_from_directory, redirect, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os, bcrypt, secrets
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ═══════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════

# Database - use environment variable for Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:1234@localhost:5432/stonevista')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Cloudinary Configuration
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

db = SQLAlchemy(app)

# ═══════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════

class User(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    phone     = db.Column(db.String(20), unique=True)
    username  = db.Column(db.String(100), unique=True)
    password  = db.Column(db.String(200))
    full_name = db.Column(db.String(200))

    def __init__(self, phone, username, password, full_name=''):
        self.phone     = phone
        self.username  = username
        self.full_name = full_name
        self.password  = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))


class Seller(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shop_name         = db.Column(db.String(200), nullable=False)
    selected_marbles  = db.Column(db.String(1000))
    address           = db.Column(db.Text)
    description       = db.Column(db.Text)
    shop_photos       = db.Column(db.Text)  # Cloudinary URLs (comma-separated)
    selected_template = db.Column(db.String(50), default='template1')
    whatsapp          = db.Column(db.String(20))
    latitude          = db.Column(db.String(20))
    longitude         = db.Column(db.String(20))
    maps_link         = db.Column(db.Text)
    email             = db.Column(db.String(200))
    years_experience  = db.Column(db.Integer, default=0)
    business_type     = db.Column(db.String(100))
    bulk_available    = db.Column(db.Boolean, default=False)
    delivery_areas    = db.Column(db.Text)


class Marble(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    filename        = db.Column(db.String(500), nullable=False)  # Cloudinary URL
    marble_name     = db.Column(db.String(200))
    marble_type     = db.Column(db.String(100))
    origin          = db.Column(db.String(200))
    finish          = db.Column(db.String(100))
    thickness       = db.Column(db.String(100))
    available_sizes = db.Column(db.String(300))
    marble_desc     = db.Column(db.Text)


class Review(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    seller_id      = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    reviewer_name  = db.Column(db.String(200), nullable=False)
    reviewer_city  = db.Column(db.String(200))
    rating         = db.Column(db.Integer, default=5)
    review_text    = db.Column(db.Text)
    review_date    = db.Column(db.Date, default=datetime.utcnow)
    verified_buyer = db.Column(db.Boolean, default=False)


class Project(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    seller_id        = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    project_title    = db.Column(db.String(200), nullable=False)
    project_type     = db.Column(db.String(100))
    project_location = db.Column(db.String(200))
    project_image    = db.Column(db.String(500))  # Cloudinary URL


with app.app_context():
    db.create_all()


# ═══════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════

def upload_to_cloudinary(file, folder):
    """Upload file to Cloudinary and return URL"""
    try:
        upload_result = cloudinary.uploader.upload(
            file,
            folder=folder,
            transformation=[
                {'width': 1200, 'height': 800, 'crop': 'limit'},
                {'quality': 'auto'},
                {'fetch_format': 'auto'}
            ]
        )
        return upload_result['secure_url']
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


# ═══════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════

@app.route('/')
@app.route('/home')
def index():
    return render_template('home.html')

@app.route('/register')
def register():
    session.clear()
    return render_template('register.html')

@app.route('/verify_phone', methods=['POST'])
def verify_phone():
    data      = request.get_json()
    phone     = data.get('phone')
    full_name = data.get('full_name', '')
    if User.query.filter_by(phone=phone).first():
        return jsonify({'success': False, 'error': 'Phone number already registered'})
    session['verified_phone']     = phone
    session['verified_full_name'] = full_name
    return jsonify({'success': True})

@app.route('/credentials', methods=['GET', 'POST'])
def credentials():
    if 'verified_phone' not in session:
        return redirect('/register')
    if request.method == 'GET':
        return render_template('credentials.html')
    username = request.form['username']
    password = request.form['password']
    if password != request.form['confirm_password']:
        return render_template('credentials.html', error='Passwords do not match')
    if User.query.filter_by(username=username).first():
        return render_template('credentials.html', error='Username already taken')
    full_name = session.pop('verified_full_name', '')
    phone     = session.pop('verified_phone')
    db.session.add(User(phone=phone, username=username, password=password, full_name=full_name))
    db.session.commit()
    session['username'] = username
    return redirect('/info')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        session.clear()
        return render_template('login.html')
    user = User.query.filter_by(username=request.form['username']).first()
    if user and user.check_password(request.form['password']):
        session['username'] = user.username
        return redirect('/dashboard' if Seller.query.filter_by(user_id=user.id).first() else '/info')
    return render_template('login.html', error='Invalid credentials')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ═══════════════════════════════════════════════════
# ONBOARDING (UPDATED FOR CLOUDINARY)
# ═══════════════════════════════════════════════════

@app.route('/info', methods=['GET', 'POST'])
def info():
    if 'username' not in session:
        return redirect('/register')
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect('/register')
    if request.method == 'GET':
        if Seller.query.filter_by(user_id=user.id).first():
            return redirect('/dashboard')
        return render_template('info.html', user=user, marbles=Marble.query.all())

    # CLOUDINARY IMAGE UPLOAD
    cloudinary_urls = []
    for photo in request.files.getlist('shop_photos'):
        if photo and photo.filename:
            url = upload_to_cloudinary(photo, f"stonevista/sellers/{user.id}")
            if url:
                cloudinary_urls.append(url)

    session['shop_info'] = {
        'shop_name':        request.form.get('shopn'),
        'address':          request.form.get('address'),
        'description':      request.form.get('description'),
        'selected_marbles': ','.join(request.form.getlist('selected_marbles')),
        'shop_photos':      ','.join(cloudinary_urls),  # Cloudinary URLs
        'whatsapp':         request.form.get('whatsapp', ''),
        'latitude':         request.form.get('latitude', ''),
        'longitude':        request.form.get('longitude', ''),
        'maps_link':        request.form.get('maps_link', ''),
    }
    return redirect('/selecttemp')

@app.route('/selecttemp', methods=['GET', 'POST'])
def selecttemp():
    if 'username' not in session or 'shop_info' not in session:
        return redirect('/register')
    if request.method == 'GET':
        return render_template('selecttemp.html', templates=['template1', 'template2', 'template3'])
    si   = session['shop_info']
    user = User.query.filter_by(username=session['username']).first()
    db.session.add(Seller(
        user_id=user.id, shop_name=si['shop_name'],
        address=si.get('address',''), description=si.get('description',''),
        selected_marbles=si.get('selected_marbles',''), shop_photos=si.get('shop_photos',''),
        selected_template=request.form.get('template'),
        whatsapp=si.get('whatsapp',''), latitude=si.get('latitude',''),
        longitude=si.get('longitude',''), maps_link=si.get('maps_link',''),
    ))
    db.session.commit()
    session.pop('shop_info', None)
    flash('Your website is ready!')
    return redirect('/dashboard')


# ═══════════════════════════════════════════════════
# PUBLIC SELLER PAGE
# ═══════════════════════════════════════════════════
@app.route('/seller/<username>')
def seller_website(username):
    user   = User.query.filter_by(username=username).first_or_404()
    seller = Seller.query.filter_by(user_id=user.id).first_or_404()
 
    marble_ids = seller.selected_marbles.split(',') if seller.selected_marbles else []
    marbles    = Marble.query.filter(Marble.id.in_(marble_ids)).all()
 
    reviews  = Review.query.filter_by(seller_id=seller.id).order_by(Review.review_date.desc()).all()
    projects = Project.query.filter_by(seller_id=seller.id).all()
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0
 
    return render_template(
        f'{seller.selected_template}.html',
        seller=seller,
        user=user,
        marbles=marbles,
        reviews=reviews,
        projects=projects,
        avg_rating=avg_rating
    )

@app.route('/preview_template/<template_name>')
def preview_template(template_name):
    if 'shop_info' in session:
        si = session['shop_info']
        marble_ids = si.get('selected_marbles','').split(',') if si.get('selected_marbles') else []
        marbles    = Marble.query.filter(Marble.id.in_(marble_ids)).all()
        class PS:
            shop_name=si.get('shop_name','My Shop'); address=si.get('address','')
            description=si.get('description',''); shop_photos=si.get('shop_photos','')
            whatsapp=si.get('whatsapp',''); latitude=si.get('latitude','')
            longitude=si.get('longitude',''); maps_link=si.get('maps_link','')
            email=years_experience=business_type=bulk_available=delivery_areas=''
        return render_template(f'{template_name}.html', seller=PS(), marbles=marbles,
                               user=None, reviews=[], projects=[], avg_rating=0)
    if 'username' in session:
        user   = User.query.filter_by(username=session['username']).first()
        seller = Seller.query.filter_by(user_id=user.id).first()
        if not seller: return redirect('/info')
        marble_ids = seller.selected_marbles.split(',') if seller.selected_marbles else []
        marbles    = Marble.query.filter(Marble.id.in_(marble_ids)).all()
        reviews    = Review.query.filter_by(seller_id=seller.id).all()
        projects   = Project.query.filter_by(seller_id=seller.id).all()
        avg_rating = round(sum(r.rating for r in reviews)/len(reviews),1) if reviews else 0
        return render_template(f'{template_name}.html', seller=seller, user=user,
                               marbles=marbles, reviews=reviews, projects=projects, avg_rating=avg_rating)
    return redirect('/login')


# ═══════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════

def _get_user_seller():
    user   = User.query.filter_by(username=session['username']).first()
    seller = Seller.query.filter_by(user_id=user.id).first()
    return user, seller

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/info')
    
    # Get reviews and projects for dashboard display
    reviews = Review.query.filter_by(seller_id=seller.id).all()
    projects = Project.query.filter_by(seller_id=seller.id).all()
    avg_rating = round(sum(r.rating for r in reviews)/len(reviews),1) if reviews else 0
    
    return render_template('dashboard.html', 
                         user=user, 
                         seller=seller,
                         reviews=reviews,
                         projects=projects,
                         avg_rating=avg_rating)


# ═══════════════════════════════════════════════════
# EDIT ROUTES (UPDATED FOR CLOUDINARY)
# ═══════════════════════════════════════════════════

@app.route('/edit_info', methods=['GET', 'POST'])
def edit_info():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/info')
    
    if request.method == 'GET':
        return render_template('edit_info.html', user=user, seller=seller, marbles=Marble.query.all())
    
    # Upload new photos to Cloudinary
    new_photos = []
    for photo in request.files.getlist('shop_photos'):
        if photo and photo.filename:
            url = upload_to_cloudinary(photo, f"stonevista/sellers/{user.id}")
            if url:
                new_photos.append(url)
    
    # Combine old and new photos
    existing_photos = request.form.get('existing_photos', '').split(',')
    existing_photos = [p for p in existing_photos if p]  # Remove empty strings
    all_photos = existing_photos + new_photos
    
    seller.shop_name = request.form.get('shopn')
    seller.address = request.form.get('address')
    seller.description = request.form.get('description')
    seller.selected_marbles = ','.join(request.form.getlist('selected_marbles'))
    seller.shop_photos = ','.join(all_photos)
    seller.whatsapp = request.form.get('whatsapp', '')
    seller.latitude = request.form.get('latitude', '')
    seller.longitude = request.form.get('longitude', '')
    seller.maps_link = request.form.get('maps_link', '')
    
    db.session.commit()
    flash('Shop information updated successfully!')
    return redirect('/dashboard')

@app.route('/edit_photos', methods=['GET', 'POST'])
def edit_photos():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/dashboard')
    
    if request.method == 'GET':
        return render_template('edit_photos.html', seller=seller)
    
    # Upload new photos to Cloudinary
    new_urls = []
    for photo in request.files.getlist('new_photos'):
        if photo and photo.filename:
            url = upload_to_cloudinary(photo, f"stonevista/sellers/{user.id}")
            if url:
                new_urls.append(url)
    
    # Get existing photos that weren't deleted
    kept_photos = request.form.getlist('keep_photos')
    all_photos = kept_photos + new_urls
    
    seller.shop_photos = ','.join(all_photos)
    db.session.commit()
    flash('Photos updated successfully!')
    return redirect('/dashboard')

@app.route('/edit_marbles', methods=['GET', 'POST'])
def edit_marbles():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/dashboard')
    
    if request.method == 'GET':
        return render_template('edit_marbles.html', seller=seller, marbles=Marble.query.all())
    
    seller.selected_marbles = ','.join(request.form.getlist('selected_marbles'))
    db.session.commit()
    flash('Selected marbles updated!')
    return redirect('/dashboard')

@app.route('/edit_template', methods=['GET', 'POST'])
def edit_template():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/dashboard')
    
    if request.method == 'GET':
        return render_template('edit_template.html', seller=seller, templates=['template1','template2','template3'])
    
    seller.selected_template = request.form.get('template')
    db.session.commit()
    flash('Template changed successfully!')
    return redirect('/dashboard')


# ═══════════════════════════════════════════════════
# REVIEWS & PROJECTS (UPDATED FOR CLOUDINARY)
# ═══════════════════════════════════════════════════

@app.route('/edit_reviews', methods=['GET', 'POST'])
def edit_reviews():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/dashboard')
    
    if request.method == 'GET':
        reviews = Review.query.filter_by(seller_id=seller.id).all()
        return render_template('edit_reviews.html', seller=seller, reviews=reviews)
    
    db.session.add(Review(
        seller_id=seller.id,
        reviewer_name=request.form.get('reviewer_name'),
        reviewer_city=request.form.get('reviewer_city'),
        rating=int(request.form.get('rating', 5)),
        review_text=request.form.get('review_text'),
        verified_buyer=request.form.get('verified_buyer') == 'on'
    ))
    db.session.commit()
    flash('Review added successfully!')
    return redirect('/edit_reviews')

@app.route('/delete_review/<int:review_id>')
def delete_review(review_id):
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    review = Review.query.get_or_404(review_id)
    if review.seller_id == seller.id:
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted')
    return redirect('/edit_reviews')

@app.route('/edit_projects', methods=['GET', 'POST'])
def edit_projects():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/dashboard')
    
    if request.method == 'GET':
        projects = Project.query.filter_by(seller_id=seller.id).all()
        return render_template('edit_projects.html', seller=seller, projects=projects)
    
    # Upload project image to Cloudinary
    project_image_url = None
    project_image = request.files.get('project_image')
    if project_image and project_image.filename:
        project_image_url = upload_to_cloudinary(project_image, f"stonevista/projects/{seller.id}")
    
    db.session.add(Project(
        seller_id=seller.id,
        project_title=request.form.get('project_title'),
        project_type=request.form.get('project_type'),
        project_location=request.form.get('project_location'),
        project_image=project_image_url
    ))
    db.session.commit()
    flash('Project added successfully!')
    return redirect('/edit_projects')

@app.route('/delete_project/<int:project_id>')
def delete_project(project_id):
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    project = Project.query.get_or_404(project_id)
    if project.seller_id == seller.id:
        db.session.delete(project)
        db.session.commit()
        flash('Project deleted')
    return redirect('/edit_projects')

@app.route('/edit_marble_detail/<int:marble_id>', methods=['GET', 'POST'])
def edit_marble_detail(marble_id):
    if 'username' not in session: return redirect('/login')
    marble = Marble.query.get_or_404(marble_id)
    
    if request.method == 'GET':
        return render_template('edit_marble_detail.html', marble=marble)
    
    marble.marble_name = request.form.get('marble_name')
    marble.marble_type = request.form.get('marble_type')
    marble.origin = request.form.get('origin')
    marble.finish = request.form.get('finish')
    marble.thickness = request.form.get('thickness')
    marble.available_sizes = request.form.get('available_sizes')
    marble.marble_desc = request.form.get('marble_desc')
    
    db.session.commit()
    flash('Marble details updated!')
    return redirect('/edit_marbles')


if __name__ == '__main__':
    app.run(debug=os.environ.get('DEBUG', 'False') == 'True')