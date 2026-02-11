from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>✅ Aplicação Funcionando!</h1><p>Versão minimal para teste</p>"

@app.route("/test")
def test():
    return {"status": "OK", "message": "API funciona"}

if __name__ == "__main__":
    app.run()
