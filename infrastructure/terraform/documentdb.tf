resource "aws_docdb_subnet_group" "db_subnets" {
  name       = "${var.project_name}-docdb-subnet-group"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-docdb-subnet-group"
  }
}

resource "aws_security_group" "docdb_sg" {
  name        = "${var.project_name}-docdb-sg"
  description = "Allow inbound MongoDB/DocDB traffic from EKS worker nodes"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow MongoDB access from EKS nodes"
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.main.vpc_config[0].cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-docdb-sg"
  }
}

resource "aws_docdb_cluster" "mongodb" {
  cluster_identifier      = "${var.project_name}-mongodb-cluster"
  engine                  = "docdb"
  master_username         = var.db_username
  master_password         = var.db_password
  db_subnet_group_name    = aws_docdb_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.docdb_sg.id]
  skip_final_snapshot     = true
  apply_immediately       = true

  tags = {
    Name        = "${var.project_name}-mongodb-cluster"
    Environment = var.environment
  }
}

resource "aws_docdb_cluster_instance" "cluster_instances" {
  count              = 1
  identifier         = "${var.project_name}-mongodb-instance-${count.index}"
  cluster_identifier = aws_docdb_cluster.mongodb.id
  instance_class     = "db.t3.medium"

  tags = {
    Name        = "${var.project_name}-mongodb-instance-${count.index}"
    Environment = var.environment
  }
}
