import aws_cdk as cdk
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_iam as iam
from cdk_nag import AwsSolutionsChecks, NagSuppressions, NagPackSuppression

class DyndnsStack(cdk.Stack):

    def __init__(self, scope: cdk.App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #Define function name if required
        runtime_function_name  = cdk.CfnParameter(
            self,
            "ddFunction", #this is what the user can pass as --parameters ddFunction="your_name"
            type="String",
            description="Provide the function name for the runtime",
            default="test_name"
        )
     
        
        #Create dynamoDB table
        table = dynamodb.Table(self, "dyndns_db",
            partition_key=dynamodb.Attribute(name="hostname", type=dynamodb.AttributeType.STRING),
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        
        #Create Lambda role
        fn_role = iam.Role(self, "dyndns_fn_role",
            assumed_by = iam.ServicePrincipal("lambda.amazonaws.com"),
            description = "DynamicDNS Lambda role",
            inline_policies = {
                'r53': iam.PolicyDocument(
                    statements = [
                        iam.PolicyStatement(
                            effect = iam.Effect.ALLOW,
                            resources = [
                                "*"
                            ],
                          actions = [
                                "route53:ChangeResourceRecordSets","route53:ListResourceRecordSets"
                            ]
                        )
                    ],
                ),
                'cw': iam.PolicyDocument(
                    statements = [
                        iam.PolicyStatement(
                            effect = iam.Effect.ALLOW,
                            resources = [
                                "*"
                            ],
                          actions = [
                                "logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"
                            ]
                        )
                    ],
                )
            }
        ) 


        if runtime_function_name.value_as_string !="":
            fn = lambda_.Function(self, "dyndns_fn",
                runtime=lambda_.Runtime.PYTHON_3_10,
                architecture=lambda_.Architecture.ARM_64,
                handler="index.lambda_handler",
                code=lambda_.Code.from_asset("lambda"),
                role=fn_role,
                function_name=runtime_function_name.value_as_string,
                #Provide DynammoDB table name as enviroment variable
                environment={
                 "ddns_config_table":table.table_name
                }
            )
        else:
            fn = lambda_.Function(self, "dyndns_fn",
                runtime=lambda_.Runtime.PYTHON_3_10,
                architecture=lambda_.Architecture.ARM_64,
                handler="index.lambda_handler",
                code=lambda_.Code.from_asset("lambda"),
                role=fn_role,
                #Provide DynammoDB table name as enviroment variable
                environment={
                 "ddns_config_table":table.table_name
                }
            )            

        #Create FunctionURL for invokation - principal will be set to * as it required for invokation from any HTTP client
        fn.add_function_url(
            #Allow unauthenticated access
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            #Set CORS for any source
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"]
            )
        )

        #Give lamdba permissions to read DynamoDB table
        table.grant_read_data(fn)

        #Suppress AwsSolutions-IAM5 triggered by Resources::*
        NagSuppressions.add_resource_suppressions(
            construct= fn_role,
            suppressions=[
                NagPackSuppression(
                    id = 'AwsSolutions-IAM5',
                    reason="""
                    Lamdba role created at line 29 has 2 inline policies allowing access to Route53 and CloudWatch. 
                    Route53 resources are set to "*" as the function will need to access any hosted zone.
                    CloudWatch resources are set to "*" to avoid having to specigy a Logging group and consume the default one deployed by CDK.
                    """
                )
            ]
        )
