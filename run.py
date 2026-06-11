from app import create_app, db

app = create_app()

# 启动入口
if __name__ == '__main__':
    app.run(debug=True)
