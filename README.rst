=================
Opwen cloudserver
=================

.. image:: https://travis-ci.org/ascoderu/opwen-cloudserver.svg?branch=master
  :target: https://travis-ci.org/ascoderu/opwen-cloudserver

.. image:: https://pyup.io/repos/github/ascoderu/opwen-cloudserver/shield.svg
  :target: https://pyup.io/repos/github/ascoderu/opwen-cloudserver/

.. image:: https://codecov.io/gh/ascoderu/opwen-cloudserver/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ascoderu/opwen-cloudserver

------------
What's this?
------------

This repository contains the source code for the Lokole cloud server. Its
purpose is to connect the `application <https://github.com/ascoderu/opwen-webapp>`_
running on the Lokole devices to the rest of the world. Lokole is a project
by the Canadian-Congolese non-profit `Ascoderu <https://ascoderu.ca>`_.

The server is implemented using `Connexion <https://jobs.zalando.com/tech/blog/crafting-effective-microservices-in-python/>`_
and has two main responsibilities:

1. Receive emails from the internet that are addressed to Lokole users and
   forward them to the appropriate Lokole device.
2. Send new emails created by Lokole users to the rest of the internet.

More background information can be found in the `opwen-webapp README <https://github.com/ascoderu/opwen-webapp/blob/master/README.rst>`_.

---------------
System overview
---------------

.. image:: https://user-images.githubusercontent.com/1086421/50498160-5eed3500-0a0c-11e9-888b-830140cd2986.png
  :width: 800
  :align: center
  :alt: Overview of the Lokole system
  :target: https://user-images.githubusercontent.com/1086421/50498160-5eed3500-0a0c-11e9-888b-830140cd2986.png

--------------------
Data exchange format
--------------------

In order to communicate between the Lokole cloud server and the Lokole email
application, a protocol based on gzipped jsonl files uploaded to Azure Blob
Storage is used. The files contains a JSON object per line. Each JSON object
describes an email, using the following schema:

.. sourcecode :: json

  {
    "sent_at": "yyyy-mm-dd HH:MM",
    "to": ["email"],
    "cc": ["email"],
    "bcc": ["email"],
    "from": "email",
    "subject": "string",
    "body": "html",
    "attachments": [{"filename": "string", "content": "base64"}]
  }

-----------------
Development setup
-----------------

First, get the source code.

.. sourcecode :: sh

  git clone git@github.com:ascoderu/opwen-cloudserver.git
  cd opwen-cloudserver

Second, install the system-level dependencies using your package manager,
e.g. on Ubuntu:

.. sourcecode :: sh

  sudo apt-get install -y make python3 python3-venv shellcheck jq

You can use the makefile to verify your checkout by running the tests and
other CI steps such as linting. The makefile will automatically install all
required dependencies into a virtual environment.

.. sourcecode :: sh

  make tests lint

This project consists of a number of microservices and background jobs. You
can run all the pieces via the makefile, however, it's easiest to run and
manage all of the moving pieces via Docker, so install Docker on your machine
by following the `Docker setup instructions <https://docs.docker.com/install/>`_
for your platform.

After installing Docker, you can run the application stack with one command:

.. sourcecode :: sh

  make run

Finding your way around the project
===================================

There are OpenAPI specifications that document the functionality of the
application and provide references to the entry points into the code
(look for the yaml files in the swagger directory). The various
APIs can also be easily called via the testing console that is available
by adding /ui to the end of the API's URL. Sample workflows are shown
below.

.. sourcecode :: sh

  # precondition:
  # register a new client
  curl "http://localhost:8080/api/email/register/" \
    -H "Content-Type: application/json" \
    -u "admin:password" \
    -d '{"domain":"developer.lokole.ca"}' \
  | tee register.json

  # workflow 1:
  # simulate delivering emails from client to online email provider
  emails_to_send="./tests/files/end_to_end/client-emails.jsonl.gz"
  client_id="$(jq -r '.client_id' < register.json)"
  resource_container="$(jq -r '.resource_container' < register.json)"
  resource_id="$(python3 -c 'import uuid;print(str(uuid.uuid4()))')"
  cp "${emails_to_send}" "./volumes/data/client-blobs/${resource_container}/${resource_id}"
  curl "http://localhost:8080/api/email/upload/${client_id}" \
    -H "Content-Type: application/json" \
    -d '{"resource_id":"'"${resource_id}"'"}'

  # workflow 2a:
  # simulate receiving email sent from online email provider to client
  email_to_receive="./tests/files/end_to_end/inbound-email.mime"
  client_id="$(jq -r '.client_id' < register.json)"
  curl "http://localhost:8080/api/email/sendgrid/${client_id}" \
    -H "Content-Type: multipart/form-data" \
    -F "email=$(cat "${email_to_receive}")"

  # workflow 2b:
  # simulate delivering emails sent from online email provider to client
  client_id="$(jq -r '.client_id' < register.json)"
  resource_container="$(jq -r '.resource_container' < register.json)"
  curl "http://localhost:8080/api/email/download/${client_id}" \
    -H "Accept: application/json" \
  | tee download.json
  resource_id="$(jq -r '.resource_id' < download.json)"
  echo "./volumes/data/client-blobs/${resource_container}/${resource_id}"

Note that by default the application is run in a fully local mode, without
leveraging any cloud services. For most development purposes this is fine
but if you wish to set up the full end-to-end stack that leverages the
same services as we use in production, keep on reading.

Integration setup
=================

The project uses Sendgrid, so to emulate a full production environment,
follow these `Sendgrid setup instructions <https://sendgrid.com/free/>`_ to
create a free account and take note of you API key for sending emails.

The project also makes use of a number of Azure services such as Blobs,
Tables, Queues, Application Insights, and so forth. To set up all the
required cloud resources programmatically, you'll need to create a service
principal by following these `Service Principal instructions <https://aka.ms/create-sp>`_.
After you created the service principal, you can run the Docker setup script
to initialize the required cloud resources.

.. sourcecode :: sh

  cat > ${PWD}/secrets/sendgrid.env << EOM
  LOKOLE_SENDGRID_KEY={the sendgrid key you created earlier}
  EOM

  cat > ${PWD}/secrets/cloudflare.env << EOM
  LOKOLE_CLOUDFLARE_USER={the cloudflare user you created earlier}
  LOKOLE_CLOUDFLARE_KEY={the cloudflare key you created earlier}
  LOKOLE_CLOUDFLARE_ZONE={the cloudflare zone you created earlier}
  EOM

  cat > ${PWD}/secrets/nginx.env << EOM
  REGISTRATION_USERNAME={some username for the registration endpoint}
  REGISTRATION_PASSWORD={some password for the registration endpoint}
  EOM

  docker build -t setup -f docker/setup/Dockerfile .

  docker run \
    -e SP_APPID={appId field of your service principal} \
    -e SP_PASSWORD={password field of your service principal} \
    -e SP_TENANT={tenant field of your service principal} \
    -e SUBSCRIPTION_ID={subscription id of your service principal} \
    -e LOCATION={an azure location like eastus} \
    -e RESOURCE_GROUP_NAME={the name of the resource group to create or reuse} \
    -v ${PWD}/secrets:/secrets \
    setup

The secrets to access the Azure resources created by the setup script will be
stored in files in the :code:`secrets` directory. Other parts of the
project's tooling (e.g. docker-compose) depend on these files so make sure to
not delete them.

To run the project using the Azure resources created by the setup, use the
following command:

.. sourcecode :: sh

  docker-compose -f docker-compose.yml -f docker-compose.secrets.yml up --build

---------------------
Production deployment
---------------------

To set up a production-ready deployment of the system, follow the development
setup scripts described above, but additionally also pass the following
environment variables to the Docker setup script:

- :code:`KUBERNETES_RESOURCE_GROUP_NAME`: The resource group into which to
  provision the Azure Kubernetes Service cluster.

- :code:`KUBERNETES_NODE_COUNT`: The number of VMs to provision into the
  cluster. This should be an odd number and can be dynamically changed later
  via the Azure CLI.

- :code:`KUBERNETES_NODE_SKU`: The type of VMs to provision into the cluster.
  This should be one of the supported `Linux VM sizes <https://docs.microsoft.com/en-us/azure/virtual-machines/linux/sizes>`_.

The script will then provision a cluster in Azure Kubernetes Service and
install the project via Helm. The secrets to connect to the provisioned
cluster will be stored in the :code:`secrets` directory.
