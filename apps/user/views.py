from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from user.models import User
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from django.http import HttpResponse
from django.core.mail import send_mail
from celery_tasks.tasks import send_register_active_email
import re
# Create your views here.


def register(request):
    """显示注册页面"""
    if request.method == 'GET':
        # 显示注册页面
        return render(request, 'register.html')
    else:
        # 接收数据
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据的校验
        if not all([user_name, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验正则
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:  # 用户名存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务的处理： 用户注册
        user = User.objects.create_user(user_name, email, password)
        user.is_active = 0
        user.save()

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


def register_handle(request):
    """进行注册的处理"""
    # 接收数据
    user_name = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    # 进行数据的校验
    if not all([user_name, password, email]):
        # 数据不完整
        return render(request, 'register.html', {'errmsg': '数据不完整'})

    # 校验正则
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

    if allow != 'on':
        return render(request, 'register.html', {'errmsg': '请同意协议'})

    # 校验用户名是否重复
    try:
        user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        # 用户名不存在
        user = None
    if user:  # 用户名存在
        return render(request, 'register.html', {'errmsg': '用户名已存在'})
    # 进行业务的处理： 用户注册
    user = User.objects.create_user(user_name, email, password)
    user.is_active = 0
    user.save()

    # 返回应答,跳转首页
    return redirect(reverse('goods:index'))


class RegisterView(View):
    """注册"""
    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """进行注册"""
        # 接收数据
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据的校验
        if not all([user_name, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验正则
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:  # 用户名存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务的处理： 用户注册
        user = User.objects.create_user(user_name, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活的链接：http://127.0.0.1:8000/user/active/1
        # 激活链接中需要包含用户的身份信息，并且要把身份信息进行加密
        # 加密用户的身份信息，生成激活的token
        serializer = Serializer(settings.SECRET_KEY, 3600)  # 一小时后过期
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # bytes需要转成string
        token = token.decode('utf8')  # 默认可以省略urf8
        # 发邮件
        send_register_active_email.delay(email, user_name, token)

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """用户激活"""
    def get(self, request, token):
        """进行用户激活"""
        # 进行解密。获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    """登录"""
    def get(self, request):
        """显示登录页面"""
        return render(request, 'login.html')
