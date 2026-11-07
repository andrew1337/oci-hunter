provider "oci" {}

resource "oci_core_instance" "generated_oci_core_instance" {
	agent_config {
		is_management_disabled = "false"
		is_monitoring_disabled = "false"
		plugins_config {
			desired_state = "DISABLED"
			name = "WebLogic Management Service"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Vulnerability Scanning"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Oracle Java Management Service"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "OS Management Hub Agent"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Management Agent"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Fleet Application Management Service"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Custom Logs Monitoring"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute RDMA GPU Monitoring"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Compute Instance Run Command"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Compute Instance Monitoring"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute HPC RDMA Auto-Configuration"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Compute HPC RDMA Authentication"
		}
		plugins_config {
			desired_state = "ENABLED"
			name = "Cloud Guard Workload Protection"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Block Volume Management"
		}
		plugins_config {
			desired_state = "DISABLED"
			name = "Bastion"
		}
	}
	availability_config {
		recovery_action = "RESTORE_INSTANCE"
	}
	availability_domain = "rjTF:eu-amsterdam-1-AD-1"
	compartment_id = "ocid1.tenancy.oc1..aaaaaaaaua32jgnzrrisvps3lxiug3uzayv67piq2fa6himfzih6cmevh5eq"
	create_vnic_details {
		assign_ipv6ip = "false"
		assign_private_dns_record = "true"
		assign_public_ip = "false"
		subnet_id = "${oci_core_subnet.generated_oci_core_subnet.id}"
	}
	display_name = "instance-20261104-2333"
	instance_options {
		are_legacy_imds_endpoints_disabled = "true"
	}
	is_pv_encryption_in_transit_enabled = "true"
	metadata = {
		"ssh_authorized_keys" = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDxx2b8nGi30+GDMALZ9qrlmTrJ1e546WbOPZRHkgpuX3+PHStSoR5+vR5yfE+rhQrx6WZKSP1dmFTdcLol1k1E3Jq31b0Ez5kjUj1t8hZjV72EaCxmrFm+Gzum/KJarFIV54/HEI9YP1aA/f5rkdt3c3f8T4iOUu5MbllujKD+6jX/sryL8+yTkpnwiZCkJTuW1EgmINEnc87ETpubdWQlcM7f8YerOc2pG5WoD88pC/csgkrUvLtEKw7VAeQa5avVNLGd/V/5a/zXNlyRKq92CS/STNfkbcA4NiYRhBkHWS067i8BH8Oun4QllvPTPloEsG6+e6s2Qyh0n0wkj28T ssh-key-2026-11-04"
	}
	shape = "VM.Standard.A1.Flex"
	shape_config {
		memory_in_gbs = "6"
		ocpus = "1"
	}
	source_details {
		boot_volume_size_in_gbs = "128"
		boot_volume_vpus_per_gb = "10"
		source_id = "ocid1.image.oc1.eu-amsterdam-1.aaaaaaaaqbfj7wndbpt555qfgzaatmbu2nr6j4dohk6uwb3dsccim5uhsnhq"
		source_type = "image"
	}
}

resource "oci_core_vcn" "generated_oci_core_vcn" {
	cidr_block = "10.0.0.0/16"
	compartment_id = "ocid1.tenancy.oc1..aaaaaaaaua32jgnzrrisvps3lxiug3uzayv67piq2fa6himfzih6cmevh5eq"
	display_name = "vcn-20261104-2334"
	dns_label = "vcn11042337"
}

resource "oci_core_subnet" "generated_oci_core_subnet" {
	cidr_block = "10.0.0.0/24"
	compartment_id = "ocid1.tenancy.oc1..aaaaaaaaua32jgnzrrisvps3lxiug3uzayv67piq2fa6himfzih6cmevh5eq"
	display_name = "subnet-20261104-2334"
	dns_label = "subnet11042337"
	route_table_id = "${oci_core_vcn.generated_oci_core_vcn.default_route_table_id}"
	vcn_id = "${oci_core_vcn.generated_oci_core_vcn.id}"
}

resource "oci_core_internet_gateway" "generated_oci_core_internet_gateway" {
	compartment_id = "ocid1.tenancy.oc1..aaaaaaaaua32jgnzrrisvps3lxiug3uzayv67piq2fa6himfzih6cmevh5eq"
	display_name = "Internet Gateway vcn-20261104-2334"
	enabled = "true"
	vcn_id = "${oci_core_vcn.generated_oci_core_vcn.id}"
}

resource "oci_core_default_route_table" "generated_oci_core_default_route_table" {
	route_rules {
		destination = "0.0.0.0/0"
		destination_type = "CIDR_BLOCK"
		network_entity_id = "${oci_core_internet_gateway.generated_oci_core_internet_gateway.id}"
	}
	manage_default_resource_id = "${oci_core_vcn.generated_oci_core_vcn.default_route_table_id}"
}
