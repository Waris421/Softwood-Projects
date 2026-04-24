from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    '''
        Custom function to convert all the built-in exceptions to the standard format
    '''
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, dict):
            if 'detail' in response.data:
                response.data['message'] = response.data.pop('detail')
            
            elif 'message' not in response.data:
                errorMsgs = []

                for field, errors in response.data.items():
                    errorMsgs.append(f"{field}: {errors[0]}")
                
                response.data = {'message': ", ".join(errorMsgs)}
        elif isinstance(response.data, list):
            response.data = {'message': response.data[0]}
    
    return response