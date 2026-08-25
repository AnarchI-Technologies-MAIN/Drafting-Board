import subprocess

caddyfile_content = """{
	admin 127.0.0.1:2019
	auto_https off
}

http://:8080 {
	bind 127.0.0.1
	encode zstd gzip

	log {
		output file /var/log/caddy/anarchi-access.log {
			roll_size 10MiB
			roll_keep 5
		}
		format filter {
			wrap json
			fields {
				request>uri delete
				request>headers delete
			}
		}
	}

	route {
		@cloudSpine host cloud.anarchi-tech.com
		handle @cloudSpine {
			reverse_proxy 127.0.0.1:10000 {
				header_up X-Anarchi-Tunnel-Token {$ANARCHI_TUNNEL_TOKEN}
			}
		}

		@retired path /cerberus/* /staging/*
		handle @retired {
			respond "{\\"status\\":\\"gone\\",\\"replacement\\":null,\\"reason\\":\\"canonical-spine-not-deployed\\"}" 410 {
				close
			}
		}

		handle /blog* {
			reverse_proxy 127.0.0.1:3080
		}

		handle /wsrs {
			redir /wsrs/ 308
		}

		handle_path /wsrs/* {
			reverse_proxy 127.0.0.1:14000 {
				header_up X-Anarchi-Tunnel-Token {$ANARCHI_TUNNEL_TOKEN}
			}
		}

		@wsrsCompatibility path /api/checkout* /api/status* /api/upgrade* /api/reviews* /api/webhooks/stripe*
		handle @wsrsCompatibility {
			reverse_proxy 127.0.0.1:14000 {
				header_up X-Anarchi-Tunnel-Token {$ANARCHI_TUNNEL_TOKEN}
			}
		}

		@public host anarchi-tech.com www.anarchi-tech.com
		handle @public {
			reverse_proxy 127.0.0.1:11000
		}

		handle /health {
			respond "{\\"service\\":\\"anarchi-local-cloud\\",\\"status\\":\\"ok\\"}" 200 {
				close
			}
		}

		handle {
			respond "{\\"service\\":\\"anarchi-local-cloud\\",\\"routes\\\":[\\"/health\\"]}" 200 {
				close
			}
		}
	}
}
"""

with open('/etc/caddy/Caddyfile', 'w', encoding='utf-8') as f:
    f.write(caddyfile_content)

print("[CADDY] Updated /etc/caddy/Caddyfile successfully.")
