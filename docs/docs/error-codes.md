# Status & Error Codes

This page documents the status codes and error messages that may be returned by the AP Manager API.

## Status Codes

Commonly used HTTP Response codes are in the service. It makes proper usage of these HTTP Status Codes and tries not to abuse their semantics. The following subset is used and documented in the respective [OpenAPI document](openapi.md):

* 200 OK - request has succeeded
* 400 Bad Request - request not processed due to a request/client error
* 404 Not Found - cannot find the requested resource
* 500 Internal Server Error - encountered an unexpected condition that prevented the service from fulfilling the request
