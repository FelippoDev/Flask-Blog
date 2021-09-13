from flask.helpers import url_for
from wtforms import meta
from flaskblog.models import User, Post
from flask import Flask, render_template, flash, redirect, request, abort
from wtforms.form import Form
from flaskblog.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, RequestResetForm, ResetPasswordForm
from flaskblog import app, db, bcrypt, mail
from flask_login import login_user, current_user, logout_user, login_required
import secrets
import os
from PIL import Image
from flask_mail import Message

@app.route("/")
@app.route("/home")
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=3)
    return render_template('index.html', posts=posts)


@app.route("/user/<string:username>")
def user_posts(username): 
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page, per_page=3)
    return render_template('posts_user.html', posts=posts,  user=user)



@app.route("/about")
def about():
    return render_template('about.html')


@app.route("/register", methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect("/")
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Your account has been created! You are able now to log in', 'success')
        return redirect("/login")
    return render_template("register.html", form=form, title='Register')


@app.route("/login", methods=['POST', 'GET'])
def login():
    if current_user.is_authenticated:
        return redirect("/")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect("/")
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template("login.html", form=form, title='Login')


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/login")

# Function for saving the image in the folder
def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    # Resizing the image
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/account", methods=['POST', 'GET'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        user = User.query.filter_by(id=current_user.id).first()
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            user.image_file = picture_file
        user.username = form.username.data
        user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated.', 'success')
        return redirect("/account")
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email

    # Path of the image
    img_file = url_for('static', filename=f'profile_pics/{current_user.image_file}')

    return render_template('account.html', title='Account Page', image=img_file, form=form) 


@app.route("/post/new", methods=['POST', 'GET'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        new_post = Post(title=form.title.data, content=form.content.data, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()
        flash('Post created successfully.', 'success')
        return redirect("/")
    return render_template("create_post.html", title="New Post", form=form)


@app.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    return render_template("post.html", post=post, title=post.title)

@app.route("/post/<int:id>/update", methods=['GET', 'POST'])
@login_required
def post_update(id):
    form = PostForm()
    post = Post.query.get_or_404(id)
    if post.user_id != current_user.id:
        abort(403)
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash("Your post has been updated.", "info")
        return redirect("/")
    elif request.method == 'GET':
        form.title.data =  post.title
        form.content.data = post.content
    return render_template("update_post.html", form=form, title='Update Post')

@app.route("/post/delete/<int:id>")
def post_delete(id):
    post = Post.query.get_or_404(id)
    if post.user_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Your post has been deleted.", 'info')
    return redirect("/")


def send_request_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender='noreply@demo.com', recipients=[user.email])
    msg.body = f""" To reset your password, visit the following link:
    {url_for('reset_token', token=token, _external=True)}
    If you did not make this request then simply ignore this email and no change will be made."""
    mail.send(msg)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect("/")
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_request_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect("/login")
    return render_template('reset_request.html', form=form, title='Reset Password')



@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect("/")
    user = User.verify_reset_token(token)
    if not user:
        flash('There is an invalid or expired token', 'warning')
        return redirect("/reset_request")
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash("Your password has been updated!", 'info')
        return redirect("/login")

    return render_template("reset_token.html", form=form, title='Reset Password')


    