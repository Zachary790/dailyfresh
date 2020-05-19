# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import time
# 在任务处理者一端加上django的配置，
# 进入虚拟环境之后任务处理端运行这个命令，在window10环境测试有效；celery -A celery_tasks.tasks worker --pool=solo -l info
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()


# 创建一个Celery类的实例对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/0', backend='redis://127.0.0.1:6379/0')


# 定义任务函数
@app.task
def send_register_active_email(to_email, user_name, token):
    """发送激活邮件"""
    subject = '天天生鲜欢迎信息'
    message = ''
    html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>' \
                   '请点击下面链接激活您的账户<br/>' \
                   '<a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' \
                   % (user_name, token, token)
    sender = settings.EMAIL_FROM
    reveiver = [to_email]
    # send_mail 是django的内置发邮箱函数，是阻塞的
    send_mail(subject, message, sender, reveiver, html_message=html_message)
    time.sleep(5)
