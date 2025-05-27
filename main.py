from datetime import date, datetime
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, ContactForm
import smtplib
import os
from dotenv import load_dotenv

# laoding environment variables
load_dotenv()
my_email = os.getenv("MY_EMAIL")
password = os.getenv("PASSWORD")



# function for sending emails
def send_mail(name, email, phone, message):
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(user=my_email, password=password)
        connection.sendmail(
            from_addr=my_email,
            to_addrs=my_email,
            msg=f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\n Message: {message}"
        )


# decorator for admin-only rights
def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function

# decorator for authenticated user rights
def user_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        comment_user = db.session.execute(db.select(Comment).where(Comment.author_id==current_user.id)).scalar()
        if current_user.is_anonymous or current_user.id != comment_user.author_id:
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function


# Initialize the flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

#Configuring Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


#  Flask-Gravatar for profile images in comments
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", 'sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES

# Create a User table for all your registered users.
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)

    # posts and comments are lists of objects of the BlogPost and Comments classes and have many-to-one relationship
    posts: Mapped[list["BlogPost"]] = relationship("BlogPost", back_populates="author")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("user.id"))
    author: Mapped["User"] = relationship("User", back_populates="posts")

    comments_on_post: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent_post")



class Comment(db.Model):
    __tablename__ = "comments"
    id:Mapped[int] = mapped_column(Integer, primary_key=True)
    text:Mapped[str] = mapped_column(String(250), nullable=False)
    comment_time:Mapped[str] = mapped_column(String(250), nullable=False)

    author_id:Mapped[int] = mapped_column(Integer, db.ForeignKey("user.id"))
    comment_author:Mapped["User"] = relationship("User", back_populates="comments")

    post_id:Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post: Mapped["BlogPost"] = relationship("BlogPost", back_populates="comments_on_post")

with app.app_context():
    db.create_all()


# User loader callback used by Flask-Login to load a user from the session
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# Registering user
# Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    registeration_form = RegisterForm()
    if registeration_form.validate_on_submit():
        reg_email = registeration_form.email.data
        reg_name = registeration_form.name.data
        reg_password = registeration_form.password.data
        if db.session.execute(db.select(User).where(User.email==reg_email)).scalar() is None:
            new_user = User(
                email=reg_email,
                name=reg_name,
                password=generate_password_hash(reg_password, method='pbkdf2:sha256', salt_length=8)
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
        else:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
    return render_template("register.html", form=registeration_form)


# User Login
# Retrieves a user from the database based on their email.
@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        paswword = login_form.password.data
        user = db.session.execute(db.select(User).where(User.email==email)).scalar()
        if user:
            if check_password_hash(user.password, paswword):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Password incorrect, please try again.")
        else:
            flash("This email does not exist, please try again.")

    return render_template("login.html", form=login_form)


# Log out the current user
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# Display all posts on the home page
@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# Display the requested blog post
# Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if comment_form.validate_on_submit():
        if current_user.is_authenticated:

            new_comment = Comment(
                text=comment_form.comment.data,
                comment_author=current_user,
                parent_post=requested_post,
                comment_time=datetime.now().strftime("at %H:%M on %B %d, %Y")

            )
            print(comment_form.comment.data)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, form=comment_form)


# Creates a new post
@app.route("/new-post", methods=["GET", "POST"])
# Only admin(first registered user) can create a new post
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# Edit an existing post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
# Only admin(first registered user) can edit a post
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# Delete a post
@app.route("/delete/<int:post_id>")
# Only admin(first registered user) can delete a post
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# Delete a comment
@app.route("/delete-comment/<int:comment_id>")
# Users can only delete their own comments
@user_only
def delete_comment(comment_id):
    comment_to_delete = db.get_or_404(Comment, comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=comment_to_delete.post_id))

# Display the about page
@app.route("/about")
def about():
    return render_template("about.html")

# Display the contact page
@app.route("/contact", methods=["GET", "POST"])
def contact():
    contact_form = ContactForm()
    if contact_form.validate_on_submit():
        name = contact_form.name.data
        email = contact_form.email.data
        phone = contact_form.phone.data
        message = contact_form.message.data

        # Send an email using the send_mail function to the admin
        send_mail(name, email, phone, message)
        return redirect(url_for("contact", msg_sent=True))
    message_sent = request.args.get("msg_sent", False) == "True"
    return render_template("contact.html", form=contact_form, msg_sent=message_sent)

# Dynamically display the year in copyright
@app.context_processor
def inject_year():
    return {'year': datetime.now().year}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
