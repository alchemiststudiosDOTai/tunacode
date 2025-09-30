# Authentication

## Usage-based billing alternative: Use an OpenAI API key

If you prefer to pay-as-you-go, you can still authenticate with your OpenAI API key:

```shell
tunacode login --api-key "your-api-key-here"
```

This key must, at minimum, have write access to the Responses API.

## Migrating to ChatGPT login from API key

If you've used the tunacode CLI before with usage-based billing via an API key and want to switch to using your ChatGPT plan, follow these steps:

1. Update the CLI and ensure `tunacode --version` is `0.20.0` or later
2. Delete `~/.tunacode/auth.json` (on Windows: `C:\\Users\\USERNAME\\.tunacode\\auth.json`)
3. Run `tunacode login` again

## Connecting on a "Headless" Machine

Today, the login process entails running a server on `localhost:1455`. If you are on a "headless" server, such as a Docker container or are `ssh`'d into a remote machine, loading `localhost:1455` in the browser on your local machine will not automatically connect to the webserver running on the _headless_ machine, so you must use one of the following workarounds:

### Authenticate locally and copy your credentials to the "headless" machine

The easiest solution is likely to run through the `tunacode login` process on your local machine such that `localhost:1455` _is_ accessible in your web browser. When you complete the authentication process, an `auth.json` file should be available at `$tunacode_HOME/auth.json` (on Mac/Linux, `$tunacode_HOME` defaults to `~/.tunacode` whereas on Windows, it defaults to `%USERPROFILE%\\.tunacode`).

Because the `auth.json` file is not tied to a specific host, once you complete the authentication flow locally, you can copy the `$tunacode_HOME/auth.json` file to the headless machine and then `tunacode` should "just work" on that machine. Note to copy a file to a Docker container, you can do:

```shell
# substitute MY_CONTAINER with the name or id of your Docker container:
CONTAINER_HOME=$(docker exec MY_CONTAINER printenv HOME)
docker exec MY_CONTAINER mkdir -p "$CONTAINER_HOME/.tunacode"
docker cp auth.json MY_CONTAINER:"$CONTAINER_HOME/.tunacode/auth.json"
```

whereas if you are `ssh`'d into a remote machine, you likely want to use [`scp`](https://en.wikipedia.org/wiki/Secure_copy_protocol):

```shell
ssh user@remote 'mkdir -p ~/.tunacode'
scp ~/.tunacode/auth.json user@remote:~/.tunacode/auth.json
```

or try this one-liner:

```shell
ssh user@remote 'mkdir -p ~/.tunacode && cat > ~/.tunacode/auth.json' < ~/.tunacode/auth.json
```

### Connecting through VPS or remote

If you run tunacode on a remote machine (VPS/server) without a local browser, the login helper starts a server on `localhost:1455` on the remote host. To complete login in your local browser, forward that port to your machine before starting the login flow:

```bash
# From your local machine
ssh -L 1455:localhost:1455 <user>@<remote-host>
```

Then, in that SSH session, run `tunacode` and select "Sign in with ChatGPT". When prompted, open the printed URL (it will be `http://localhost:1455/...`) in your local browser. The traffic will be tunneled to the remote server. 
