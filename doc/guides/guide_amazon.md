# Perspectives: Set Up a Free Notary Server in 15 minutes with AWS

Originally posted by Dan Wendtland at http://perspectives-project.org/2011/07/04/aws-notary-server/

This document has been updated for the current version of [Perspectives server](https://github.com/danwent/Perspectives-Server).

## Introduction

Amazon Web Services (AWS) let's you easily create a server in the "cloud".  In fact, they even let you run a "micro" instance for free, thanks to something called the "free usage tier".

This guide will show you how you can get your own notary running in just 15 minutes using AWS.


## Requirements

* A valid credit card, required to create an Amazon AWS account


## Cost

Free up to the limits specified in the [Free Usage Tier](https://aws.amazon.com/free/).

As of this writing:
* 750 hours of EC2 Micro Instance usage (enough to run one instance the entire month)
* 750 hours of Single-AZ Micro DB Instances (enough to run one database the entire month)
* 30 GB of Elastic Block Storage (EBS), plus 2 million I/Os and 1 GB of snapshot storage
* 20 GB of database storage
* 15 GB of bandwidth out


**Caution:** While setting up a micro ec2 instance is free, if you use a larger instance type or run an intensive process, Amazon will charge you money. You may wish to set up Amazon alerts to notify you of usage beyond the free tier limits, and/or use the ```--quiet``` option when performing scans.


## Setup

1. First, [read about the free usage tier and sign up for an AWS account](http://aws.amazon.com/free/).

2. Then access the [AWS management console](https://aws.amazon.com/console/) to create a machine instance.

3. Create an account and log in! Then click on the "EC2" tab near the top left of the screen.


**Note:** any line beginning with ```>``` is a unix command. You can run these inside your terminal/command prompt window.


## Create an SSH Keypair

You will need a SSH keypair, which will automatically be installed onto the Amazon machine instance that you launch. This allows you to access the instance remotely without a password.

There are two options for creating keypairs: letting Amazon generate the keypair, and creating it yourself. Letting Amazon generate the keys can be faster, but you have no guarantee that they key has not be copied. Generating a keypair yourself is more secure, and doesn't take long.

**IMPORTANT! :** Regardless of the method you choose, be sure to save a copy of the key file and store it somewhere safe! You will need the key file to access your ec2 machine.

Official documentation:
http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html


### (Option 1) Let Amazon generate the keys

Inside the EC2 dashboard click on 'Key Pairs' and 'Create Key Pair'. Enter a name (e.g., 'notary-key') and click the 'Yes' button. Amazon will send you a .pem file - save this file someplace safe.

After downloading the key, make sure it is only accessible to your user:

```>chmod 600 notary.pem```


### (Option 2) Create your own keypair

The official documentation is here:
http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#how-to-generate-your-own-key-and-import-it-to-aws

Install the program 'ssh-keygen'. If you are running linux this is likely already installed. Then run this in a command prompt:

```>ssh-keygen -t rsa -b 2048 -C "notary aws key file"```

This creates an RSA type key of length 2048 bits.
You can enter whatever comment you like in the -C flag above.
The program will then ask you for a name and an optional passphrase.
Once the files are generated, store them someplace safe!

After you have your key files, go back to the AWS dashboard. Inside the EC2 dashboard click on 'Key Pairs' and 'Import Key Pair'. You can then browse to or copy/paste the *public* key.

**IMPORTANT! :** Make sure to upload the *public* key - the one that ends with '.pub'. That's the key Amazon will install on your EC2 machine. You will use the corresponding *private* key to log in using ssh - do not share the private key with anyone you do not trust!


## Amazon Setup

Now we're ready to launch a machine!

Click the "Launch Instance" button in the EC2 dashboard.

Choose an Ubuntu server AMI by clicking on the "Community AMIs" tab and finding a matching image. Here are a couple things to keep in mind:

* Make sure the image is free tier eligible (denoted by a yellow star or the text "Free tier eligible").
* Use an image with a "Root Store" of "ebs", as this means that even if this particular instance dies, you can spin up a new instance and reattach the same disk. This ensures you do not lose your data.
* We recommend [encrypting](https://aws.amazon.com/blogs/aws/protect-your-data-with-new-ebs-encryption/) your EBS volume
* 64-bit image is suggested.
* Choosing a Long Term Support (LTS) build is advised so you can easily update packages and security fixes. You can see the exact version for an image by reading the "Manifest" field.

In the "U.S East" region, an Amazon Machine Image (AMI) that matches these criteria is: ```ami-cef405a7```. Another example is ```Ubuntu Server 12.04.3 LTS - ami-6aad335a``` .

Select your AMI, and keep the default "Micro" instance. Click the "Review and Launch" button.

Before launching the instance you should modify its "security group", which by default drops all inbound traffic.  You should open up port 22 for SSH and port 8080 for the notary webserver. Click on "Edit Security Groups" and select "Create a new security group". On the page for adding rules, select "Inbound" and add two rules:

1. Custom TCP Rule, port range = 8080, source = (Anywhere) 0.0.0.0/0 , click "Add Rule"
2. SSH, port range = 22, source = (pull down the box that says 'My IP') , click "Add Rule"
	Click "Apply Rule Changes"

While it is possible to allow SSH from any IP address, this is strongly not recommended. You should add a rule for each IP address that needs to connect, to keep the machine more secure.

When you're finished, click on the "Launch" button!

The last step is to assign your keyfile so you can connect via ssh. Select 'Use an existing key pair' and choose the key you created earlier.

Congratulations! You now have a running ec2 machine.

Note the instance ID of your new machine, so you can use it in the next step.


## Get the Instance's SSH Fingerprint

Before connecting for the first time you should verify the ssh key used by your instance. This ensures that you are connecting to the correct machine, and that your session has not been man-in-the-middle attacked (probably the same reason you use Perspectives!).

1. First, install the AWS Command Line Interface. If you have python installed, this is probably easiest using pip:

  ```>pip install awscli```

  For full instructions see https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-set-up.html#install-with-pip .

  You will need your AWS access key ID and secret acces key, [as discussed here](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-set-up.html)


2. Secondly, configure the awscli:

  ```>aws configure```

  Type or paste in your Access Key ID and Secret Access Key when asked. The full instructions are at https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html .


3. Finally, execute the 'get-console-output' command:

  ```>aws ec2 get-console-output --instance-id i-12345```

  You should see some output that includes the server's ssh key fingerprints:

		ec2: -----BEGIN SSH HOST KEY FINGERPRINTS-----
		ec2: 1024 aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99  root@ip-0-0-0-0 (DSA)
		ec2: 256  00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff  root@ip-0-0-0-0 (ECDSA)
		ec2: 2048 00:99:88:77:66:55:44:33:22:11:ff:ee:dd:cc:bb:aa  root@ip-0-0-0-0 (RSA)
		ec2: -----END SSH HOST KEY FINGERPRINTS-----


  Write down the RSA key for use in the next step.

Note that you *must* retrieve the server's ssh fingerprint the *first* time you launch the instance. If you stop the instance and re-launch it later the fingerprint will not be listed in the console output (as the ssh keys have already been installed to that instance).

The server's fingerprint will be the same after every launch, but you must read it the first time if you want to verify.


## Connect to the machine

You can now access your machine remotely.  Click on "Instances" in the left dashboard panel. Select your instance’s row in the main pane and view the details box at the bottom.  Note the "Public DNS" field, as this is how you will access the machine remotely. It will look like 'ec2-11-11-11-11.us-west-2.compute.amazonaws.com'. To connect to the machine, run:

```>ssh -i notary.pem ubuntu@<insert-public-dns>```

If the fingerprint displayed matches the one you retrieved from the previous step, you can type 'yes' and connect to the machine!


## Set up the Notary Server

Now we are on the Ubuntu server and the real fun can be begin.  We need to install the right dependencies and download the notary code.

	>sudo apt-get install git-core python-sqlite python-sqlalchemy python-m2crypto python-cherrypy3
	>git clone git://github.com/danwent/Perspectives-Server.git

This will create a folder called 'Perspectives-Server'.

Now, initialize the setup and start the webserver:

	>cd Perspectives-Server
	>chmod 770 admin/*.sh
	>admin/setup.sh
	>admin/start_webserver.sh

Now your notary is up and running!  It will respond to notary requests on port 8080 . To see the public key the notary uses to sign all requests, run:

	>cat notary.pub

This is the public key that can be provided to a Perspectives client to authenticate the notary response.

The server code comes with a simple client for you to test.  To query a website to monitor (Perspectives calls sites "service-id"s), specify it using the form 'site:port,2'. For example, to query http://www.google.com, run:

	>python client/simple_client.py www.google.com:443,2

The first time you run this query the notary server will not know about the service, and will return a 404 error. In the background the notary server will launch an "on-demand" probe for that service to fetch its key. Wait a couple seconds and run the same command again: you should now see a response.

By default (if you run setup.sh, above), the notary server will run a scan of all known service-ids twice a day, as configured using crontab. You can manually run a scan of all services at any point by running:

	>admin/start_scan.sh


And there you have it! You now have a running Perspectives notary! You can add the notary's address and public key to your Perspectives client and use it to validate sites.


For more information see the [README file](../../README.md) or the doc/ directory. Feel free to ask questions on [the mailing list](https://groups.google.com/group/perspectives-dev)!


-------


## Optional: Setting up a Relational Database Service

**Note:** As of June 2014, Amazon [no longer charges for EBS based on the amount of reads or writes performed](https://aws.amazon.com/blogs/aws/new-ssd-backed-elastic-block-storage). Thus it is no longer as necessary to host notary data inside an RDS. However, this section is left intact for anyone who wishes to do so.

You may wish to use a Relational Database Service (RDS) instead of writing to an sqlite database on disk. Data transfer between Amazon RDS and Amazon EC2 machines is free.

To set up a RDS:

- From the Amazon web console, click on "RDS" in the Database group
- On the RDS Dashboard page, click 'Launch an Instance'
- Select your desired database type, such as Postgres
- When asked about Multi-AZ Deployment, select "No", to remain in the free-usage tier.
- Under database details:
	- Select a "db.t1.micro" instance class
	- Select "No" to Multi-AZ Deployment
	- Make sure the "Use Provisioned IOPS" box is *NOT* checked
	- Choose a storage size of at least 200MB. The minimum storage for a Postgres database, for example, is 5GB, which will easily hold all of the data your notary will use.
	- choose an instance name, username, and password. Write these down somewhere safe
- On the Additional Configuration screen:
	- Set "Publicly Accessible" to No, unless you really want to connect to your database from the outside world
	- Be sure to select the same Availability Zone as your EC2 machine
	- Select the same Security Group as your EC2 machine
	- Choose any database name you like
- Fill in other options as you see fit. You may want to enable more than 1 day of automatic backups in case something goes wrong.
- You may want to specify times for your database backups and updates that do not overlap with notary scanning runs, so the database is not being used.


- Once you have created your RDS, click on the 'Instances' link and check the box next to your RDS instance. Note down the 'Endpoint', which will look something like 'instance-name.xxxxxxxxxxxx.us-west-2.rds.amazonaws.com:5432'. This is the database hostname your EC2 machine will connect to, so write it down or remember it for later.


- Next, return to the EC2 dashboard. We will need to open a port so your EC2 machine can connect to your database.

- Click on the Instances link and check the box beside your EC2 instance
- On the Description tab, note down the Private IPs, for example 172.28.11.130.

- Next click on Security Groups
- Select the security group that both your EC2 machine and your database use
- Click on the Inbound tab
- Create a new Custom TCP rule that allows your private IP to talk to the database:
	- add port 5432 (or whatever port you specified for your database)
	- You can add the EC2 machine's IP address directly (e.g. 172.28.11.130) or set up a partial mask that will allow other machines from the same part of the network; for example - 172.28.11.00/24 . This may be desirable if you plan to have multiple machines on the same private network all talking to the same database.

	See https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing for more information.

	- Click 'Apply Rule Changes' to save your filter


Your EC2 machine can now connect to your database! To instruct your notary to do so you need to pass the database arguments when running the web service and notary scans.


1. **Option 1:** Edit the 'server_args' and 'database_args' variables in ```admin/start_webserver.sh``` and ```admin/start_scan.sh```. Add the --dbtype, --dbname, --dbhost, and --dbuser values.

  Note that the database password is not stored in the configuration files but read from the 'NOTARY_DB_PASSWORD' environment variable. Set up the environment variable using the next step.

2. **Option 2:** Edit the 'server_args' and 'database_args' variables in ```admin/start_webserver.sh``` and ```admin/start_scan.sh```. Add the --dburl switch to have them both read the database connection info from the 'DATABASE_URL' environment variable. Set up the environment variable using the next step.

Note the 'DATABASE_URL' variable will take a special form depending on the type of database you connect to. It will usually be similar to ```database_type://username:password@instance-name.xxxxxxxxxxxx.us-west-2.rds.amazonaws.com:5432/db_name```.



Set up the environment variable by adding a line to admin/_common_functions.sh that uses the 'export' command:

```>export NOTARY_DB_PASSWORD=correcthorsebatterystaple```  
or  
```>export DATABASE_URL=postgres://username:password@instance-name.xxxxxxxxxxxx.us-west-2.rds.amazonaws.com:5432/db_name```

Your notary will now be able to read the correct connection settings even after rebooting.



## Advanced: Securing EC2 machines

There are many steps you can take to secure your EC2 machine, depending on what OS or AMI type you selected. Here are a few resources to get you started; contributions to this document are welcome (or start a thread on the mailing list).

### General

* [Enable EBS volume encryption when creating your volume](https://aws.amazon.com/blogs/aws/protect-your-data-with-new-ebs-encryption/)


### Ubuntu LTS 12.04

* Remove unneeded programs:

		>sudo apt-get remove telnet
		>sudo apt-get remove rlogin

* Try setting up rkhunter or fail2ban

Links:

* https://help.ubuntu.com/community/Security
* http://secure-ubuntu-server.blogspot.com/

