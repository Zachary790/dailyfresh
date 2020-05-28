from django.contrib import admin
from django.core.cache import cache
from goods.models import GoodsType, IndexPromotionBanner, GoodsImage, IndexTypeGoodsBanner, IndexGoodsBanner


class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """新增或者更新表中的数据时调用"""
        super(BaseModelAdmin, self).save_model(request, obj, form, change)
        # 发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存存储
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """删除表中的数据时调用"""
        super(BaseModelAdmin, self).delete_model(request, obj)
        # 发出任务，让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()
        # 清除首页的缓存存储
        cache.delete('index_page_data')


# Register your models here.
class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


class GoodsTypeAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
