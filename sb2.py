from sb2 import app
app.secret_key = app.config['secret_key']
app.run(host='0.0.0.0', port=app.config['port'], debug=app.config['debug'], threaded=app.config['threaded'])
