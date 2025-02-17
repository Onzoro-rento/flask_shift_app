from flask import Flask,render_template,redirect,flash,request,url_for
from flask_wtf import FlaskForm
from wtforms import (StringField,IntegerField,PasswordField,RadioField,SelectField,BooleanField,TextAreaField,SubmitField,DateField,TimeField)
from wtforms.validators import DataRequired,Length,ValidationError,Email,EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import LoginManager,UserMixin,login_user,logout_user,login_required,current_user
from datetime import datetime,date,timedelta
from collections import defaultdict

import os

app = Flask(__name__)

app.config['SECRET_KEY'] ='mysecretkey'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir,'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
Migrate(app,db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def localize_callback(*args,**kwargs):
    return 'このページにアクセスするには、ログインが必要です。'
login_manager.localize_callback = localize_callback

from sqlalchemy.engine import Engine
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

class User(UserMixin,db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer,primary_key =True)
    name = db.Column(db.String(20),unique = True,nullable = False)
    code = db.Column(db.String(50),unique = True,nullable = False)  #従業員コード
    password = db.Column(db.String(120),nullable = False)
    age = db.Column(db.Integer) #年齢
    # 各ポジションの評価（0: まったく, 1: 少し, 2: まあまあ, 3: マスター）
    menba = db.Column(db.Integer, default=0)
    yakiba = db.Column(db.Integer, default=0)
    checkout = db.Column(db.Integer, default=0)
    sikomi = db.Column(db.Integer, default=0)
    administrator = db.Column(db.String(1),default = "0")
    def set_password(self,password):
        self.password = generate_password_hash(password)
    
    def check_password(self,password):
        return check_password_hash(self.password,password)
#シフトのデータベース
class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)  # "HH:MM" 形式
    end_time = db.Column(db.Time, nullable=False)
    break_time = db.Column(db.Float,default = 0.0)
    user = db.relationship('User', backref=db.backref('shifts', lazy=True))

class LoginForm(FlaskForm):
    code = StringField('従業員コード：',validators = [DataRequired()])
    password = PasswordField('パスワード：',validators =[DataRequired()])
    submit = SubmitField('ログイン')

class SignUpForm(LoginForm):
    
    name = StringField('名前:',validators =[DataRequired()])
    age = IntegerField('年齢:',validators =[DataRequired()])
    submit = SubmitField('サインアップ')
    
    def validate_code(self,code):
        user = User.query.filter_by(code = code.data).first()
        if user:
            raise ValidationError('その従業員コードは既に使用されています')




#ログイン
@app.route("/",methods = ["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        code = form.code.data
        password = form.password.data
        
        user = User.query.filter_by(code = code).first()
        if user is not None and user.check_password(password):
            
            login_user(user)
            
            return redirect(url_for("index"))
        flash("認証不備です")
    return render_template("login.html",form = form)

#シフト追加関数
@app.route("/add_shift", methods=["GET","POST"])
@login_required
def add_shift():
    
    year = request.args.get('year', default=datetime.now().year, type=int)
    month = request.args.get('month', default=datetime.now().month, type=int)
    
    # 月の調整
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    # 当月の開始日
    start_date = date(year, month, 1)
    
    # 翌月の開始日を求める（翌月が12月を超えたら翌年にする）
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], "%Y-%m-%d").date()
        start_time = datetime.strptime(request.form['start_time'], "%H:%M").time()
        end_time = datetime.strptime(request.form['end_time'], "%H:%M").time()
        break_time = float(request.form['break_time'])
        shift = Shift(start_date = start_date,start_time = start_time,end_time = end_time,user_id = current_user.id,break_time = break_time)
        db.session.add(shift)
        db.session.commit()
        flash("シフトを登録しました")
        return redirect(url_for("index"))
    return render_template("add_shift.html",year = year,month = month)


#ログアウト
@app.route("/logout")
def logout():
    logout_user()
    flash("ログアウトしました")
    
    return redirect(url_for("login"))
#ユーザー登録
@app.route("/register",methods = ["GET","POST"])
def register():
    form = SignUpForm()
    if form.validate_on_submit():
        name = form.name.data
        age = form.age.data
        code = form.code.data
        password = form.password.data
        user = User(name = name,age = age,code = code)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("ユーザー登録しました")
        return redirect(url_for("login"))
    return render_template("sign_up.html",form = form)

#最初に表示される画面
@app.route("/index")
@login_required #ログインが必要
def index():
   
    year = request.args.get('year', default=datetime.now().year, type=int)
    month = request.args.get('month', default=datetime.now().month, type=int)
    
    # 月の調整
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    # 当月の開始日
    start_date = date(year, month, 1)
    
    # 翌月の開始日を求める（翌月が12月を超えたら翌年にする）
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    your_shift = Shift.query.filter(
        Shift.user_id == current_user.id,
        Shift.start_date >= start_date,
        Shift.start_date < end_date).order_by(Shift.start_date).all()   
    
    
     
    
    
    return render_template("home.html",year = year,month = month,your_shift = your_shift)

@app.route("/view_shift",methods=["GET"]) #シフト一覧確認
@login_required #ログインが必要
def view_shift():
    year = request.args.get('year', default=datetime.now().year, type=int)
    month = request.args.get('month', default=datetime.now().month, type=int)
    day = request.args.get('day', default=datetime.now().day, type=int)
    # 月の調整
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    # 当月の開始日
    start_date = date(year, month, 1)

    
    #当月の日数を取得
    if month < 12:
        days_in_month = (date(year, month + 1, 1) - timedelta(days=1)).day
    else:
        days_in_month = 31
    #日の調整
    if day > days_in_month:
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif day < 1:
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        days_in_month = (date(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31
        day = days_in_month
    
    
      #フォームからの入力を取得      
    start_date_str = request.args.get('start_date')
    if start_date_str:
        
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        year, month, day = start_date.year, start_date.month, start_date.day
        
            

    else:
        start_date = datetime(year, month, day).date()
            
    

    
    
    
    #指定した日のシフトを全て取得
    shifts = Shift.query.filter(Shift.start_date == start_date).all()
    
    return render_template("view_shift.html",year = year,month = month,day = day,shifts= shifts)

@app.route("/member")
@login_required
def member():
    users = User.query.order_by(User.age).all()
    return render_template("view_user.html",users = users)

#指定したユーザーを削除
@app.route('/delete/<int:user_id>',methods = ['POST'])
@login_required
def delete_user(user_id):
    user = User.query.filter_by(id = user_id).first()
    shifts = Shift.query.filter(Shift.user_id == user_id).all()
    for shift in shifts:
        db.session.delete(shift)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('member'))

#指定したユーザーを管理者に設定
@app.route('/update/<int:user_id>',methods = ['GET','POST'])
@login_required
def update_user(user_id):
    user = User.query.filter_by(id = user_id).first()
    if user.administrator == "1":
        flash('指定されたユーザーは管理者です')
        return redirect(url_for('member'))
    else:
        user.administrator = "1"
        db.session.commit()
        flash("指定したユーザーを管理者にしました")
        return redirect(url_for('member'))

#シフトのバランスを計算
@app.route('/shift_balance')
@login_required
def shift_balance():
    
    year = request.args.get('year', default=datetime.now().year, type=int)
    month = request.args.get('month', default=datetime.now().month, type=int)
    
    # 月の調整
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1
    # 当月の開始日
    start_date = date(year, month, 1)
    
    # 翌月の開始日を求める（翌月が12月を超えたら翌年にする）
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    #ある月間の全てのシフトデータ
    all_shift = Shift.query.filter(
        Shift.start_date >= start_date,
        Shift.start_date < end_date).order_by().all()   
    work_hours = defaultdict(float)
    for shift in all_shift:
        start_dt = datetime.combine(shift.start_date, shift.start_time)
        end_dt = datetime.combine(shift.start_date, shift.end_time)
        if shift.break_time is not None:
            break_time = shift.break_time
        else:
            break_time = 0
        # シフトの稼働時間（時間単位）
        duration = (end_dt - start_dt).total_seconds() / 3600
        work_hours[shift.user_id] += duration - break_time
    
    ranking = []
    for user_id, hours in work_hours.items():
        user = User.query.filter_by(id = user_id).first()
        ranking.append({'name': user.name, 'hours': hours})   
        
         
    ranking = sorted(ranking, key=lambda x: x['hours'], reverse=True)

    
        
    
     
    
    
    return render_template("shift_balance.html",year = year,month = month,ranking = ranking)
#ユーザーのスキル管理
@app.route('/skill_maintenance')
@login_required
def skill_maintenance():
    users = User.query.order_by(User.age).all()
    return render_template("skill_maintenance.html",users = users)


@app.route('/skill_update/<int:user_id>',methods = ['GET','POST'])
@login_required
def skill_update(user_id):
    user = User.query.filter_by(id = user_id).first()
    if request.method == 'POST':
        user.menba = request.form['menba']
        user.yakiba = request.form['yakiba']
        user.checkout = request.form['checkout']
        user.sikomi= request.form['sikomi']
        db.session.commit()
        flash("変更しました")
        return redirect(url_for("skill_maintenance"))
    return render_template("skill_update.html",user = user)
    



    
        
    


if __name__ == '__main__':
    app.run(debug = True)