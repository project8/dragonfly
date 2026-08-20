# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Types of changes: Added, Changed, Deprecated, Removed, Fixed, Security

## [Unreleased]


## [2.2.0] -- 2026-08-20

### Added

- AstevalFormatEntity    FormatEntity which supports asteval evaluation at formating
- CmdEntity              Class providing a CMD entity, this was implemented in dripline-cpp but not in dripline-python, can be used to e.g. call a calibrate CMD
- EthernetHuberService	 Service implementing the communication protocol used by Huber company
- HuberGetEntity	 A get entity to implement communication protocol used by Huber company
- EthernetModbusService  Service to implement modbus communication 
- ModbusEntity           Entiy for modbus communication 
- ModbusGetEntity        GetEntity for modbus communication
- ModbusSetEntity        SetEntity for modbus communication
- PfeifferEntity         Entity supporting formatting used by devices from Pfeiffer company
- PfeifferGetEntity      GetEntity supporting formatting used by devices from Pfeiffer company
- PfeifferSetEntity      SetEnitty supporting formatting used by devices from Pfeiffer company

## [2.1.1] -- 2026-02-05

### Changed

- Updated dripline-python to v5.1.5


## [2.1.0] -- 2025-10-01

### Added

- Thermo Fisher Chiller service and endpoint added
- Watchdog added
- Added prototypical Docker Compose file
- Added this changelog and GHA step to use it in making releases

### Changed

- Updated GHA workflow and Python package build
- Switch GHA Linux runners to Ubuntu 22.04
- dl-py base version updated to v5.1.0

## [2.0.1] - 2024-04-25

### Changed

- dl-py version updated to v4.7.1

## [2.0.0] -- 2022-05-26

### Changed

- First dl3 implementation
