from flask.templating import render_template
from flaskblog import app 

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('error/403.html'), 403


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error/500.html'), 500


