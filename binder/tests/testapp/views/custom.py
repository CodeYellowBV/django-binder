from django.views.decorators.http import require_GET

from binder.json import JsonResponse


@require_GET
def custom(request):
	return JsonResponse({'custom': True})

# @require_GET
# def user(request):
# 	if not request.user.is_authenticated:
# 		res = JsonResponse({})
# 		res.status_code = 403
# 		return res
#
# 	return JsonResponse({
# 		'username': request.user.username,
# 		'email': request.user.email,
# 	})
