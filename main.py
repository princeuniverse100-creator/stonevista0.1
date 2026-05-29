from flask import Flask, render_template, request, send_from_directory, redirect, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os, bcrypt, secrets
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/stonevista'
app.config['UPLOAD_FOLDER']  = 'uploads/sellers'
app.config['MARBLE_FOLDER']  = 'uploads/marbles'
app.config['PROJECT_FOLDER'] = 'uploads/projects'
app.secret_key = secrets.token_hex(32)

os.makedirs(app.config['UPLOAD_FOLDER'],  exist_ok=True)
os.makedirs(app.config['MARBLE_FOLDER'],  exist_ok=True)
os.makedirs(app.config['PROJECT_FOLDER'], exist_ok=True)

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
    shop_photos       = db.Column(db.Text)
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
    filename        = db.Column(db.String(200), nullable=False)
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
    project_image    = db.Column(db.String(200))


with app.app_context():
    db.create_all()


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
# ONBOARDING
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

    photos = []
    for photo in request.files.getlist('shop_photos'):
        if photo and photo.filename:
            fname = f"shop_{user.id}_{secure_filename(photo.filename)}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            photos.append(fname)

    session['shop_info'] = {
        'shop_name':        request.form.get('shopn'),
        'address':          request.form.get('address'),
        'description':      request.form.get('description'),
        'selected_marbles': ','.join(request.form.getlist('selected_marbles')),
        'shop_photos':      ','.join(photos),
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
        return render_template('selecttemp.html', templates=['template1', 'template2'])
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
 
    # NEW — fetch reviews and projects
    reviews  = Review.query.filter_by(seller_id=seller.id).order_by(Review.review_date.desc()).all()
    projects = Project.query.filter_by(seller_id=seller.id).all()
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0
 
    return render_template(
        f'{seller.selected_template}.html',
        seller=seller,
        user=user,
        marbles=marbles,
        reviews=reviews,       # NEW
        projects=projects,     # NEW
        avg_rating=avg_rating  # NEW
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
# FILE SERVING
# ═══════════════════════════════════════════════════

@app.route('/uploads/sellers/<filename>')
def uploaded_seller_file(filename):
    try:    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except: return "Image not found", 404

@app.route('/uploads/marbles/<filename>')
def uploaded_marble_file(filename):
    return send_from_directory(app.config['MARBLE_FOLDER'], filename)

@app.route('/uploads/projects/<filename>')
def uploaded_project_file(filename):
    return send_from_directory(app.config['PROJECT_FOLDER'], filename)


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
    reviews  = Review.query.filter_by(seller_id=seller.id).all()
    projects = Project.query.filter_by(seller_id=seller.id).all()
    return render_template('dashboard.html', user=user, seller=seller,
                           reviews=reviews, projects=projects)

@app.route('/visit')
def visit():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/info')
    return redirect(f'/seller/{user.username}')


# ── edit info ──

@app.route('/dashboard/edit/info', methods=['GET', 'POST'])
def edit_info():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if not seller: return redirect('/info')
    if request.method == 'GET':
        return render_template('edit_info.html', seller=seller, user=user)
    f = request.form
    seller.shop_name        = f.get('shop_name')
    seller.address          = f.get('address')
    seller.description      = f.get('description')
    seller.whatsapp         = f.get('whatsapp','')
    seller.email            = f.get('email','')
    seller.latitude         = f.get('latitude','')
    seller.longitude        = f.get('longitude','')
    seller.maps_link        = f.get('maps_link','')
    seller.years_experience = int(f.get('years_experience',0) or 0)
    seller.business_type    = f.get('business_type','')
    seller.bulk_available   = bool(f.get('bulk_available'))
    seller.delivery_areas   = f.get('delivery_areas','')
    db.session.commit()
    flash('Shop info updated!')
    return redirect('/dashboard')


# ── edit photos ──

@app.route('/dashboard/edit/photos', methods=['GET', 'POST'])
def edit_photos():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    if request.method == 'GET':
        return render_template('edit_photos.html', seller=seller,
                               current_photos=seller.shop_photos.split(',') if seller.shop_photos else [])
    saved = []
    for photo in request.files.getlist('shop_photos'):
        if photo and photo.filename:
            fname = f"shop_{user.id}_{secure_filename(photo.filename)}"
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            saved.append(fname)
    if saved:
        existing = seller.shop_photos.split(',') if seller.shop_photos else []
        seller.shop_photos = ','.join([p for p in existing if p] + saved)
        db.session.commit()
    flash('Photos updated!')
    return redirect('/dashboard')

@app.route('/dashboard/edit/photos/delete', methods=['POST'])
def delete_photo():
    if 'username' not in session: return redirect('/login')
    _, seller = _get_user_seller()
    fname   = request.form.get('filename')
    current = seller.shop_photos.split(',') if seller.shop_photos else []
    seller.shop_photos = ','.join([f for f in current if f != fname])
    db.session.commit()
    fp = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    if os.path.exists(fp): os.remove(fp)
    flash('Photo removed.')
    return redirect('/dashboard/edit/photos')


# ── edit marbles ──

@app.route('/dashboard/edit/marbles', methods=['GET', 'POST'])
def edit_marbles():
    if 'username' not in session: return redirect('/login')
    _, seller = _get_user_seller()
    if request.method == 'GET':
        current_ids = seller.selected_marbles.split(',') if seller.selected_marbles else []
        return render_template('edit_marbles.html', all_marbles=Marble.query.all(), current_ids=current_ids)
    seller.selected_marbles = ','.join(request.form.getlist('selected_marbles'))
    db.session.commit()
    flash('Stone selection updated!')
    return redirect('/dashboard')

@app.route('/dashboard/marble/add', methods=['POST'])
def add_marble():
    if 'username' not in session: return redirect('/login')
    _, seller = _get_user_seller()

    img_file = request.files.get('marble_image')
    if not img_file or not img_file.filename:
        flash('Please select an image.')
        return redirect('/dashboard/edit/marbles')

    # Save file with seller prefix to avoid name clashes
    fname = f"seller{seller.id}_{secure_filename(img_file.filename)}"
    img_file.save(os.path.join(app.config['MARBLE_FOLDER'], fname))

    # Create marble record
    new_marble = Marble(
        filename    = fname,
        marble_name = request.form.get('marble_name', '').strip(),
        marble_type = request.form.get('marble_type', ''),
    )
    db.session.add(new_marble)
    db.session.flush()  # get the new marble ID

    # Auto-select it for this seller
    current = seller.selected_marbles.split(',') if seller.selected_marbles else []
    current = [x for x in current if x]  # remove empty strings
    current.append(str(new_marble.id))
    seller.selected_marbles = ','.join(current)

    db.session.commit()
    flash(f'"{new_marble.marble_name or fname}" added to your catalogue!')
    return redirect('/dashboard/edit/marbles')


@app.route('/dashboard/marble/edit/<int:marble_id>', methods=['GET', 'POST'])
def edit_marble_detail(marble_id):
    if 'username' not in session: return redirect('/login')
    marble = Marble.query.get_or_404(marble_id)
    if request.method == 'GET':
        return render_template('edit_marble_detail.html', marble=marble)
    f = request.form
    marble.marble_name     = f.get('marble_name','')
    marble.marble_type     = f.get('marble_type','')
    marble.origin          = f.get('origin','')
    marble.finish          = f.get('finish','')
    marble.thickness       = f.get('thickness','')
    marble.available_sizes = f.get('available_sizes','')
    marble.marble_desc     = f.get('marble_desc','')
    new_img = request.files.get('new_image')
    if new_img and new_img.filename:
        fname = secure_filename(new_img.filename)
        new_img.save(os.path.join(app.config['MARBLE_FOLDER'], fname))
        marble.filename = fname
    db.session.commit()
    flash('Marble details updated!')
    return redirect('/dashboard/edit/marbles')


# ── edit template ──

@app.route('/dashboard/edit/template', methods=['GET', 'POST'])
def edit_template():
    if 'username' not in session: return redirect('/login')
    _, seller = _get_user_seller()
    if request.method == 'GET':
        return render_template('edit_template.html', seller=seller, templates=['template1','template2'])
    seller.selected_template = request.form.get('template')
    db.session.commit()
    flash('Template updated!')
    return redirect('/dashboard')


# ── reviews ──

@app.route('/dashboard/reviews', methods=['GET', 'POST'])
def manage_reviews():
    if 'username' not in session: return redirect('/login')
    _, seller  = _get_user_seller()
    reviews    = Review.query.filter_by(seller_id=seller.id).order_by(Review.review_date.desc()).all()
    if request.method == 'GET':
        return render_template('edit_reviews.html', seller=seller, reviews=reviews)
    f = request.form
    db.session.add(Review(
        seller_id=seller.id, reviewer_name=f.get('reviewer_name'),
        reviewer_city=f.get('reviewer_city',''), rating=int(f.get('rating',5)),
        review_text=f.get('review_text',''),
        review_date=datetime.strptime(f.get('review_date', datetime.utcnow().strftime('%Y-%m-%d')),'%Y-%m-%d').date(),
        verified_buyer=bool(f.get('verified_buyer'))
    ))
    db.session.commit()
    flash('Review added!')
    return redirect('/dashboard/reviews')

@app.route('/dashboard/reviews/delete/<int:rid>', methods=['POST'])
def delete_review(rid):
    if 'username' not in session: return redirect('/login')
    r = Review.query.get_or_404(rid)
    db.session.delete(r); db.session.commit()
    flash('Review deleted.')
    return redirect('/dashboard/reviews')


# ── projects ──

@app.route('/dashboard/projects', methods=['GET', 'POST'])
def manage_projects():
    if 'username' not in session: return redirect('/login')
    user, seller = _get_user_seller()
    projects = Project.query.filter_by(seller_id=seller.id).all()
    if request.method == 'GET':
        return render_template('edit_projects.html', seller=seller, projects=projects)
    img_file = request.files.get('project_image')
    img_fname = ''
    if img_file and img_file.filename:
        img_fname = f"proj_{seller.id}_{secure_filename(img_file.filename)}"
        img_file.save(os.path.join(app.config['PROJECT_FOLDER'], img_fname))
    f = request.form
    db.session.add(Project(
        seller_id=seller.id, project_title=f.get('project_title'),
        project_type=f.get('project_type',''), project_location=f.get('project_location',''),
        project_image=img_fname
    ))
    db.session.commit()
    flash('Project added!')
    return redirect('/dashboard/projects')

@app.route('/dashboard/projects/delete/<int:pid>', methods=['POST'])
def delete_project(pid):
    if 'username' not in session: return redirect('/login')
    p = Project.query.get_or_404(pid)
    if p.project_image:
        fp = os.path.join(app.config['PROJECT_FOLDER'], p.project_image)
        if os.path.exists(fp): os.remove(fp)
    db.session.delete(p); db.session.commit()
    flash('Project deleted.')
    return redirect('/dashboard/projects')


# ── admin ──

@app.route('/admin/add_marbles')
def add_marbles():
    if request.args.get('key') != os.environ.get('ADMIN_KEY','changeme'):
        return "Unauthorized", 403
    for i in range(1,4):
        if not Marble.query.filter_by(filename=f'marble{i}.jpg').first():
            db.session.add(Marble(filename=f'marble{i}.jpg'))
    db.session.commit()
    return "Marbles added!"


if __name__ == '__main__':
    app.run(debug=True, port=5000)