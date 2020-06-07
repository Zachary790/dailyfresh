from django.shortcuts import render, redirect
from django.views.generic import View
from django.urls import reverse
from goods.models import GoodsSKU
from user.model import Address
from order.model import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from django.http import JsonResponse
from django.db import transaction
from datetime import datetime
from alipay import AliPay
from django.conf import settings
import os

# Create your views here.


# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    """提交页面显示"""
    def post(self, request):
        """提交订单显示"""
        sku_ids = request.POST.getlist('sku_ids')
        user = request.user
        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            count = conn.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count ，保存购买商品的数量
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += count
            total_price += amount
        # 运费：属于一个子系统
        transit_price = 10  # 写死运费
        # 是付款
        total_pay = transit_price + total_price
        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)
        context = {'skus': skus,
                   'total_count': total_count,
                   'total_price': total_price,
                   'transit_price': transit_price,
                   'total_pay': total_pay,
                   'sku_ids': sku_ids,
                   'addrs': addrs}
        return render(request, 'place_order.html', context)


class OrderCommitView1(View):
    @transaction.atomic
    def post(self, request):
        """订单创建"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的校验方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})
        # 向df_order_info表中添加一条记录
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     pay_method=pay_method,
                                     total_count=total_count,
                                     total_price=total_price,
                                     transit_price=transit_price)
            sku_ids = sku_ids.split[',']
            conn = get_redis_connection('dafault')
            cart_key = 'cart_%d' % user.id
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # select * from df_good_sku where id=sku_id for update; 加悲观锁
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                    # 乐观锁，在查询数据的时候不加锁，在更新的时候进行判断，更新时的库存和查出来的库存时候一致
                except:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                # 从redis中获取用户所要购买的商品的数量
                count = conn.hget(cart_key, sku_id)
                # 判断商品的库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                # todo 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()
                # 累加计算订单商品的总数量总价格
                amount = sku.price * int(count)
                total_count += int(count)
                total_price += amount
            # 更新订单信息表中的商品总数量，总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交事务
        transaction.savepoint_commit(save_id)

        # 清楚用户购物车
        conn.hdel(cart_key, *sku_ids)
        return JsonResponse({'res': 5, 'errmsg': '创建成功'})


class OrderCommitView(View):
    @transaction.atomic
    def post(self, request):
        """订单创建"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的校验方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})
        # 向df_order_info表中添加一条记录
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     pay_method=pay_method,
                                     total_count=total_count,
                                     total_price=total_price,
                                     transit_price=transit_price)
            sku_ids = sku_ids.split[',']
            conn = get_redis_connection('dafault')
            cart_key = 'cart_%d' % user.id
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品的信息
                    try:
                        # 乐观锁，在查询数据的时候不加锁，在更新的时候进行判断，更新时的库存和查出来的库存时候一致
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)
                    # 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # todo 更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)
                    # update df_goods_sku set stock=new_stock,
                    # sales=new_sales where id=sku_id and stork = orgin_stock;
                    # 返回受影响的行数
                    res = GoodsSKU.objects.finlter(id=sku_id, stock=new_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试第三次
                            # 更新失败
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
                        continue
                    sku.stock -= int(count)
                    sku.sales += int(count)
                    sku.save()
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # 累加计算订单商品的总数量总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount
                    # 跳出循环
                    break
            # 更新订单信息表中的商品总数量，总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
        # 提交事务
        transaction.savepoint_commit(save_id)

        # 清楚用户购物车
        conn.hdel(cart_key, *sku_ids)
        return JsonResponse({'res': 5, 'errmsg': '创建成功'})


class OrderPayView(View):
    """订单支付"""
    def post(self, request):
        """订单支付"""
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接受参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})
        # 业务处理，使用pythonsdk调用支付宝的支付接口
        alipay = AliPay(
            appid="2016102800774692",
            app_notify_url=None,
            app_private_key_string=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_string=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",
            debug=True
        )
        # 调用支付接口
        total_pay = order.total_price+order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),  # 支付总金额
            subject="天天生鲜%s" % order_id,
            return_url=None,
            notify_url=None
        )
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


class CheckPayView(View):
    """查看订单支付的结果"""
    def post(self, request):
        """查询订单结果"""
        """订单支付"""
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接受参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})
        # 业务处理，使用pythonsdk调用支付宝的支付接口
        alipay = AliPay(
            appid="2016102800774692",
            app_notify_url=None,
            app_private_key_string=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_string=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type="RSA2",
            debug=True
        )

        # 交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            code = response.get('code')
            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                return JsonResponse({'res': 3, 'errmsg': '支付成功'})
                # 放回结果
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待卖家付款
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})
