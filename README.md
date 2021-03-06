# Overview

Deploy your own content distribution network (CDN).

# Usage

To deploy the charm:

    juju deploy cs:content-cache

Set juju config for the `sites` option as required. For example:

    # Site with some public, some authenticated content, using another site
    # with two IPs for authentication. In this case, 10.1.1.2 and 10.1.1.3
    # would need to listen on 443 for auth.example1.com and process
    # authentication requests. If set, cache-maxconn will set the maximum
    # number of simultaneous connections to the nginx cache for this location,
    # while backend-maxconn limits connections to the defined backends.
    # If unset, both will default to 2048
    example1.com:
      tls-cert-bundle-path: /var/lib/haproxy
      locations:
        '/':
          extra-config:
            - root /srv/example1.com/content/
            - autoindex on
        '/auth':
          modifier: '='
          backends:
            - 10.1.1.2:443
            - 10.1.1.3:443
          backend-check-path: /status
          backend-inter-time: '10s'
          backend-maxconn: 64
          backend-path: /auth-check/
          backend-tls: True
          cache-maxconn: 4096
          cache-validity: '200 401 1h'
          origin-headers:
            - Original-URI: $request_uri
            - Resource-Name: example1
          extra-config:
            - internal
            - proxy_cache_key $http_authorization
          site-name: auth.example1.com
        '/status':
          extra-config:
            - stub_status on
        '/private/content/':
          extra-config:
            - root /srv/example1.com/content/
            - autoindex on
            - auth_request /auth
          nagios-expect: 401 Unauthorized

To get metrics:

    juju deploy cs:telegraf
    juju add-relation telegraf:haproxy content-cache:haproxy-statistics

You can then query the telegraf endpoint to get HAProxy metrics from the
content-cache charm.

To get cache hits metrics:

    juju config content-cache enable_prometheus_metrics=true

This will expose the following metrics for each site configured:

    # HELP nginx_cache_request_hit_total Number of cache hits per site
    # TYPE nginx_cache_request_hit_total counter
    nginx_cache_request_hit_total{host="myhost"} 10
    # HELP nginx_cache_request_total Number of cache requests per site 
    # TYPE nginx_cache_request_total counter                           
    nginx_cache_request_total{host="myhost"} 20
    # HELP nginx_http_request_total Number of HTTP requests per site
    # TYPE nginx_http_request_total counter
    nginx_http_request_total{host="myhost",status="200"} 110129
    # HELP nginx_metric_errors_total Number of nginx-lua-prometheus errors
    # TYPE nginx_metric_errors_total counter
    nginx_metric_errors_total 0
