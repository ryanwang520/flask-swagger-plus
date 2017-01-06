# flask-swagger-plus
Extract swagger spec from source code (with `Form` and `Schema` components integrated).

## Install

```bash
pip install flask-swagger-plus
```


A Simple Example
```python
from flask import Flask, jsonify
from flask.views import MethodView
from flask_swagger_plus import Form, SwaggerResponse, StringField, form, swagger
from marshmallow import Schema, fields

class ParamsForm(Form):
    email = StringField()
    name = StringField()

class AddressSchema(Schema):
    street = fields.Str()
    state = fields.Str()
    country = fields.Str()

class UserAPI(MethodView):

    @ParamsForm
    @SwaggerResponse(AddressSchema)
    def post(self):
        """
        create a new user
        ---
        """
        print(form.email)
        print(form.name)
        return {
            'street': 'street',
            'state': 'state',
            'country': 'country'
        }


app = Flask(__name__)

app.add_url_rule('/users/', view_func=UserAPI.as_view('show_users'))


@app.route('/swagger.json')
def spec():
    return jsonify(swagger(app))

if __name__ == '__main__':
    app.run(debug=True)
```

**docstring** with _---_ is required as we can thus know if you want to export an api to swagger spec.
It's also available if you prefer to using decorator style router registry.
```python
@app.route('/post_user')
@ParamsForm
@SwaggerResponse(AddressSchema)
def post_user():
    """
    create user
    ---
    """
    return {}
```

The json result from `/swagger.json` would like
```
{
  "definitions": {
    "__main__post:AddressSchema": {
      "properties": {
        "country": {
          "type": "string"
        },
        "state": {
          "type": "string"
        },
        "street": {
          "type": "string"
        }
      }
    }
  },
  "info": {
    "title": "Cool product name",
    "version": "0.0.0"
  },
  "paths": {
    "/users/": {
      "post": {
        "description": "",
        "parameters": [
          {
            "description": "",
            "in": "formData",
            "name": "email",
            "type": "string"
          },
          {
            "description": "",
            "in": "formData",
            "name": "name",
            "type": "string"
          }
        ],
        "responses": {
          "200": {
            "description": "api result",
            "schema": {
              "$ref": "#/definitions/__main__post:AddressSchema"
            }
          }
        },
        "security": [],
        "summary": "create a new user",
        "tags": [
          "__main__"
        ]
      }
    }
  },
  "swagger": "2.0"
}
```

Hope you enjoy it!

