"""
Provides an APIView class that is the base of all views in REST framework.
"""
from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, models, transaction
from django.http import Http404
from django.http.response import HttpResponseBase
from django.utils.cache import cc_delim_re, patch_vary_headers
from django.utils.encoding import smart_text
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from rest_framework import exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.schemas import DefaultSchema
from rest_framework.settings import api_settings
from rest_framework.utils import formatting
from rest_framework.negotiation import DefaultContentNegotiation


def get_view_name(view_cls, suffix=None):
    """
    Given a view class, return a textual name to represent the view.
    This name is used in the browsable API, and in OPTIONS responses.

    This function is the default for the `VIEW_NAME_FUNCTION` setting.
    """
    name = view_cls.__name__
    name = formatting.remove_trailing_string(name, 'View')
    name = formatting.remove_trailing_string(name, 'ViewSet')
    name = formatting.camelcase_to_spaces(name)
    if suffix:
        name += ' ' + suffix

    return name


def get_view_description(view_cls, html=False):
    """
    Given a view class, return a textual description to represent the view.
    This name is used in the browsable API, and in OPTIONS responses.

    This function is the default for the `VIEW_DESCRIPTION_FUNCTION` setting.
    """
    description = view_cls.__doc__ or ''
    description = formatting.dedent(smart_text(description))
    if html:
        return formatting.markup_description(description)
    return description


def set_rollback():
    atomic_requests = connection.settings_dict.get('ATOMIC_REQUESTS', False)
    if atomic_requests and connection.in_atomic_block:
        transaction.set_rollback(True)


def exception_handler(exc, context):
    """
    Returns the response that should be used for any given exception.

    By default we handle the REST framework `APIException`, and also
    Django's built-in `Http404` and `PermissionDenied` exceptions.

    Any unhandled exceptions may return `None`, which will cause a 500 error
    to be raised.
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (list, dict)):
            data = exc.detail
        else:
            data = {'detail': exc.detail}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    return None


class APIView(View):

    # The following policies may be set at either globally, or per-view.
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES
    # 给客户端返回数据时默认使用的数据转化类
    # 'DEFAULT_RENDERER_CLASSES': (
    #     'rest_framework.renderers.JSONRenderer', # 返回json字符串
    #     'rest_framework.renderers.BrowsableAPIRenderer', # 针对浏览器WebApi返回的网页
    # ),

    parser_classes = api_settings.DEFAULT_PARSER_CLASSES
    # 默认解析请求体数据的解析器类
    # 'DEFAULT_PARSER_CLASSES': (
    #     'rest_framework.parsers.JSONParser',
    #     'rest_framework.parsers.FormParser',
    #     'rest_framework.parsers.MultiPartParser'
    # ),
    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    # 默认的认证模型类
    # 'DEFAULT_AUTHENTICATION_CLASSES': (
    #    'rest_framework.authentication.SessionAuthentication', #使用session认证
    #    'rest_framework.authentication.BasicAuthentication',#使用HTTP默认认证
    # ),
    throttle_classes = api_settings.DEFAULT_THROTTLE_CLASSES
    # 默认的限流类,这里默认情况下不对接口进行限流
    # 'DEFAULT_THROTTLE_CLASSES': (),
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES
    # 默认的用户授权类
    # 'DEFAULT_PERMISSION_CLASSES': (
    #     'rest_framework.permissions.AllowAny',# 默认不对用户任何限制
    # ),
    content_negotiation_class = api_settings.DEFAULT_CONTENT_NEGOTIATION_CLASS
    # 默认的内容判别类;用于识别出请求数据类型,并且制定请求数据解析器,以及识别出客户端需要的数据类型,并且制定相应数据渲染器
    # 'DEFAULT_CONTENT_NEGOTIATION_CLASS': 'rest_framework.negotiation.DefaultContentNegotiation',
    metadata_class = api_settings.DEFAULT_METADATA_CLASS
    # 默认的元数据类 ,客户端发情OPTIONS请求时,使用这个类来构建响应数据 最后的options方法回去调用他
    # DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    versioning_class = api_settings.DEFAULT_VERSIONING_CLASS
    # 默认的接口版本识别类,用于识别出客户端请求的接口版本
    #  'DEFAULT_VERSIONING_CLASS': None,
    # Allow dependency injection of other settings to make testing easier.
    settings = api_settings

    schema = DefaultSchema()

    @classmethod
    def as_view(cls, **initkwargs):
        """
        Store the original class on the view function.

        This allows us to discover information about the view when we do URL
        reverse lookups.  Used for breadcrumb generation.
        """
        # 价差queryset属性是不是django的QuerySet对象;通常定义queryset=ClassModel.objects.all()
        if isinstance(getattr(cls, 'queryset', None), models.query.QuerySet):
            def force_evaluation():
                raise RuntimeError(
                    'Do not evaluate the `.queryset` attribute directly, '
                    'as the result will be cached and reused between requests. '
                    'Use `.all()` or call `.get_queryset()` instead.'
                )
            # django中查询所有数据是通过_fetch_all方法来执行的
            cls.queryset._fetch_all = force_evaluation
        # 调用View返回的view视图函数 view中回去调用dispatch方法
        view = super(APIView, cls).as_view(**initkwargs)
        # 给视图函数指明类名和以及初始化参数,方便在异常处理中去调用
        view.cls = cls
        view.initkwargs = initkwargs

        # Note: session based authentication is explicitly CSRF validated,
        # all other authentication is CSRF exempt.
        return csrf_exempt(view)

    @property
    def allowed_methods(self):
        """
        Wrap Django's private `_allowed_methods` interface in a public property.
        """
        # 默认是['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
        return self._allowed_methods()

    @property
    def default_response_headers(self):
        # 响应头中的Allow: 客户端允许使用的请求方法
        # 默认是['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
        headers = {
            'Allow': ', '.join(self.allowed_methods),
        }

        # 如果有多个渲染器的话,就是服务器支持多个响应数据类型默认json和浏览器web
        if len(self.renderer_classes) > 1:
            headers['Vary'] = 'Accept'
        return headers

    def http_method_not_allowed(self, request, *args, **kwargs):
        """
        If `request.method` does not correspond to a handler method,
        determine what kind of exception to raise.
        """
        raise exceptions.MethodNotAllowed(request.method)

    def permission_denied(self, request, message=None):
        """
        If request is not permitted, determine what kind of exception to raise.
        """
        # 如果没有权限的话,那么要不放回未认证要么返回没有权限
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        raise exceptions.PermissionDenied(detail=message)

    def throttled(self, request, wait):
        """
        If request is throttled, determine what kind of exception to raise.
        """
        raise exceptions.Throttled(wait)

    def get_authenticate_header(self, request):
        """
        If a request is unauthenticated, determine the WWW-Authenticate
        header to use for 401 responses, if any.
        """
        # 授权头
        authenticators = self.get_authenticators()
        if authenticators:
            return authenticators[0].authenticate_header(request)

    def get_parser_context(self, http_request):
        """
        Returns a dict that is passed through to Parser.parse(),
        as the `parser_context` keyword argument.
        """
        # Note: Additionally `request` and `encoding` will also be added
        #       to the context by the Request object.
        # 请求数据解析器的上下文
        return {
            'view': self,
            'args': getattr(self, 'args', ()),
            'kwargs': getattr(self, 'kwargs', {})
        }

    def get_renderer_context(self):
        """
        Returns a dict that is passed through to Renderer.render(),
        as the `renderer_context` keyword argument.
        """
        # Note: Additionally 'response' will also be added to the context,
        #       by the Response object.
        # 渲染器的上下文
        return {
            'view': self,
            'args': getattr(self, 'args', ()),
            'kwargs': getattr(self, 'kwargs', {}),
            'request': getattr(self, 'request', None)
        }

    def get_exception_handler_context(self):
        """
        Returns a dict that is passed through to EXCEPTION_HANDLER,
        as the `context` argument.
        """
        # 异常处理的上下文
        return {
            'view': self,
            'args': getattr(self, 'args', ()),
            'kwargs': getattr(self, 'kwargs', {}),
            'request': getattr(self, 'request', None)
        }

    def get_view_name(self):
        """
        Return the view name, as used in OPTIONS responses and in the
        browsable API.
        """
        func = self.settings.VIEW_NAME_FUNCTION
        return func(self.__class__, getattr(self, 'suffix', None))

    def get_view_description(self, html=False):
        """
        Return some descriptive text for the view, as used in OPTIONS responses
        and in the browsable API.
        """
        func = self.settings.VIEW_DESCRIPTION_FUNCTION
        return func(self.__class__, html)

    # API policy instantiation methods

    def get_format_suffix(self, **kwargs):
        """
        Determine if the request includes a '.json' style format suffix
        """
        if self.settings.FORMAT_SUFFIX_KWARG:
            return kwargs.get(self.settings.FORMAT_SUFFIX_KWARG)

    def get_renderers(self):
        """
        Instantiates and returns the list of renderers that this view can use.
        """
        return [renderer() for renderer in self.renderer_classes]

    def get_parsers(self):
        """
        Instantiates and returns the list of parsers that this view can use.
        """
        # 默认是
        # [rest_framework.parsers.JSONParser(),
        # rest_framework.parsers.FormParser(),
        # rest_framework.parsers.MultiPartParser()]
        return [parser() for parser in self.parser_classes]

    def get_authenticators(self):
        """
        Instantiates and returns the list of authenticators that this view can use.
        """
        # 默认是 SessionAuthentication 和 BasicAuthentication
        return [auth() for auth in self.authentication_classes]

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        return [permission() for permission in self.permission_classes]

    def get_throttles(self):
        """
        Instantiates and returns the list of throttles that this view uses.
        """
        return [throttle() for throttle in self.throttle_classes]

    def get_content_negotiator(self):
        """
        Instantiate and return the content negotiation class to use.
        """
        # 默认是 DefaultContentNegotiation
        if not getattr(self, '_negotiator', None):
            self._negotiator = self.content_negotiation_class()
        return self._negotiator

    def get_exception_handler(self):
        """
        Returns the exception handler that this view uses.
        """
        return self.settings.EXCEPTION_HANDLER

    # API policy implementation methods

    def perform_content_negotiation(self, request, force=False):
        """
        Determine which renderer and media type to use render the response.
        """
        # 确认客户端渲染器来给客户端返回数据
        renderers = self.get_renderers()
        conneg = self.get_content_negotiator()

        try:
            return conneg.select_renderer(request, renderers, self.format_kwarg)
        except Exception:
            if force:
                return (renderers[0], renderers[0].media_type)
            raise

    def perform_authentication(self, request):
        """
        Perform authentication on the incoming request.

        Note that if you override this and simply 'pass', then authentication
        will instead be performed lazily, the first time either
        `request.user` or `request.auth` is accessed.
        """
        #  掉用Request对象的user方法,执行用户认证
        request.user

    def check_permissions(self, request):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """
        # 验证是否可以查询多个数据
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )

    def check_object_permissions(self, request, obj):
        """
        Check if the request should be permitted for a given object.
        Raises an appropriate exception if the request is not permitted.
        """
        # 验证是否有权限获取单个模型对象
        for permission in self.get_permissions():
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )

    def check_throttles(self, request):
        """
        Check if request should be throttled.
        Raises an appropriate exception if the request is throttled.
        """
        # 验证是否超过限流范围了
        for throttle in self.get_throttles():
            if not throttle.allow_request(request, self):
                self.throttled(request, throttle.wait())

    def determine_version(self, request, *args, **kwargs):
        """
        If versioning is being used, then determine any API version for the
        incoming request. Returns a two-tuple of (version, versioning_scheme)
        """
        # 默认没有版本类
        # 识别出客户端发起的请求使用的版本
        if self.versioning_class is None:
            return (None, None)
        scheme = self.versioning_class()
        return (scheme.determine_version(request, *args, **kwargs), scheme)

    # Dispatch methods

    def initialize_request(self, request, *args, **kwargs):
        """
        Returns the initial request object.
        """
        # 构建用于解析请求体数据是的上下文
        # parser_context={
        #     'view': self,
        #     'args': getattr(self, 'args', ()),
        #     'kwargs': getattr(self, 'kwargs', {})
        # }
        parser_context = self.get_parser_context(request)

        return Request(
            request,
            parsers=self.get_parsers(),
            authenticators=self.get_authenticators(),
            negotiator=self.get_content_negotiator(),
            parser_context=parser_context
        )

    def initial(self, request, *args, **kwargs):
        """
        Runs anything that needs to occur prior to calling the method handler.
        """
        self.format_kwarg = self.get_format_suffix(**kwargs)

        # Perform content negotiation and store the accepted info on the request

        # 根据客户端的请求对向,自动识别出需要用哪一个渲染器来渲染数据给客户端
        # 返回的渲染器和媒体类型
        neg = self.perform_content_negotiation(request)
        # 保存渲染器和媒体类型到request对象中,用于后面对响应数据进行渲染
        request.accepted_renderer, request.accepted_media_type = neg

        # Determine the API version, if versioning is in use.
        # 识别出版本号
        version, scheme = self.determine_version(request, *args, **kwargs)
        # 版本号以及版本识别类对象
        request.version, request.versioning_scheme = version, scheme

        # Ensure that the incoming request is permitted
        # 用户认证
        self.perform_authentication(request)
        # 权限检查
        self.check_permissions(request)
        # 限流检查
        self.check_throttles(request)

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Returns the final response object.
        """
        # Make the error obvious if a proper response is not returned
        assert isinstance(response, HttpResponseBase), (
            'Expected a `Response`, `HttpResponse` or `HttpStreamingResponse` '
            'to be returned from the view, but received a `%s`'
            % type(response)
        )

        if isinstance(response, Response):
            # 自动检查客户端需要返回的数据类型
            if not getattr(request, 'accepted_renderer', None):
                neg = self.perform_content_negotiation(request, force=True)
                request.accepted_renderer, request.accepted_media_type = neg

            response.accepted_renderer = request.accepted_renderer
            response.accepted_media_type = request.accepted_media_type
            response.renderer_context = self.get_renderer_context()

        # Add new vary headers to the response instead of overwriting.
        vary_headers = self.headers.pop('Vary', None)
        if vary_headers is not None:
            patch_vary_headers(response, cc_delim_re.split(vary_headers))

        # 设置响应头
        for key, value in self.headers.items():
            response[key] = value

        return response

    def handle_exception(self, exc):
        """
        Handle any exception that occurs, by returning an appropriate response,
        or re-raising the error.
        """
        if isinstance(exc, (exceptions.NotAuthenticated,
                            exceptions.AuthenticationFailed)):
            # WWW-Authenticate header for 401 responses, else coerce to 403
            auth_header = self.get_authenticate_header(self.request)

            if auth_header:
                exc.auth_header = auth_header
            else:
                exc.status_code = status.HTTP_403_FORBIDDEN

        exception_handler = self.get_exception_handler()

        context = self.get_exception_handler_context()
        response = exception_handler(exc, context)

        # 如果异常类型没有被处理(也就是异常处理函数需要返回response对象)那么抛出异常信息
        if response is None:
            self.raise_uncaught_exception(exc)

        response.exception = True
        return response

    def raise_uncaught_exception(self, exc):
        if settings.DEBUG:
            # 根据需要返回json,html以及api数据类型
            request = self.request
            renderer_format = getattr(request.accepted_renderer, 'format')
            use_plaintext_traceback = renderer_format not in (
                'html', 'api', 'admin')
            request.force_plaintext_errors(use_plaintext_traceback)
        raise

    # Note: Views are made CSRF exempt from within `as_view` as to prevent
    # accidental removal of this exemption in cases where `dispatch` needs to
    # be overridden.
    def dispatch(self, request, *args, **kwargs):
        """
        `.dispatch()` is pretty much the same as Django's regular dispatch,
        but with extra hooks for startup, finalize, and exception handling.
        """
        # 把view中传递进来的参数赋值给当前类视图对象
        # URL分组匿名args与命名参数kwargs
        self.args = args
        self.kwargs = kwargs
        # 初始化request对象 返回的是Request对象
        request = self.initialize_request(request, *args, **kwargs)
        # request赋值给当前类视图对象
        self.request = request
        # 计算默认的响应头
        self.headers = self.default_response_headers  # deprecate?

        try:
            #
            self.initial(request, *args, **kwargs)

            # Get the appropriate handler method
            # 调用类对象中请求方法对应的小写方法
            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(),
                                  self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed

            response = handler(request, *args, **kwargs)

        except Exception as exc:
            # 如果抛出异常就由异常处理函数进行处理 默认是 exception_handler可以通过配置进行指定
            response = self.handle_exception(exc)
        # 最终返回resonse对象
        self.response = self.finalize_response(
            request, response, *args, **kwargs)
        return self.response

    def options(self, request, *args, **kwargs):
        """
        Handler method for HTTP 'OPTIONS' request.
        """

        if self.metadata_class is None:
            return self.http_method_not_allowed(request, *args, **kwargs)
        data = self.metadata_class().determine_metadata(request, self)
        return Response(data, status=status.HTTP_200_OK)
