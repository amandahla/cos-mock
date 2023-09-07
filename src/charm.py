#!/usr/bin/env python3
# Copyright 2023 Amanda
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""This charm mock COS charms."""

import logging
import requests
import hashlib
import json
import typing

from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointConsumer
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardConsumer
import ops

logger = logging.getLogger(__name__)

PEER = "grafana"

class CosMockCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.metrics_consumer = MetricsEndpointConsumer(self)
        self.dashboard_consumer = GrafanaDashboardConsumer(self)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(
        self.metrics_consumer.on.targets_changed,
        self._on_scrape_targets_changed)
        self.framework.observe(
        self.dashboard_consumer.on.dashboards_changed,
        self._on_dashboards_changed)

    def _on_config_changed(self, _):
        self.unit.status = ops.ActiveStatus("Ready to go")

    def _on_scrape_targets_changed(self, event):
        logger.debug("scrape_target_changed received")
        try:
            scrape_jobs = self.metrics_consumer.jobs()
            if len(scrape_jobs) == 0:
                logger.debug("No jobs received")
                return
            logger.debug(scrape_jobs)
            self.unit.status = ops.MaintenanceStatus("Testing targets")
            targets_found = 0
            logger.debug("%d scrape jobs found", len(scrape_jobs))
            for job in scrape_jobs:
                static_configs = job['static_configs']
                metrics_path = job['metrics_path']
                logger.debug("%d static_configs found", len(static_configs))
                for config in static_configs:
                    targets = config['targets']
                    logger.debug("metrics_path: %s targets: %s",metrics_path, targets)
                    for target in targets:
                        url = f"http://{target}{metrics_path}"
                        logger.debug("requesting %s", url)
                        res = requests.get(url, timeout=5)
                        res.raise_for_status()
                        logger.debug("success!Next...")
                        targets_found +=1
            if len(scrape_jobs) > 0 and targets_found == 0:
                logger.debug("No targets received")
                self.unit.status = ops.BlockedStatus("No targets received")
                return
            logger.debug("%d targets found", targets_found)
            logger.debug("Test succeed")
            self.unit.status = ops.ActiveStatus("Ready to go")
        except Exception as ex:
            logger.exception(ex)
            self.unit.status = ops.BlockedStatus(str(ex))

    def _on_dashboards_changed(self, _) -> None:
        logger.debug("dashboards_changed received")
        dashboards_found = 0
        self.unit.status = ops.MaintenanceStatus("Testing dashboards")
        dashboards = self.dashboard_consumer.dashboards
        try:
            for dashboard in dashboards:
                dashboard_content = dashboard["content"]
                dashboard_content_bytes = dashboard_content.encode("utf-8")
                json.loads(dashboard_content_bytes)
                logger.debug("received valid json file")
                dashboard_content_digest = hashlib.sha256(dashboard_content_bytes).hexdigest()
                dashboard_filename = "juju_{}_{}.json".format(
                    dashboard["charm"], dashboard_content_digest[0:7]
                )
                logger.debug("dashboard_filename: %s", dashboard_filename)
                dashboards_found+=1
        except Exception as ex:
            logger.exception(ex)
            self.unit.status = ops.BlockedStatus(str(ex))
        if len(dashboards) > 0 and dashboards_found == 0:
                logger.debug("No dashboards received")
                self.unit.status = ops.BlockedStatus("No dashboards received")
                return
        logger.debug("%d dashboards found", dashboards_found)
        self.unit.status = ops.ActiveStatus("Ready to go")

    @property
    def has_peers(self) -> bool:
        """Check whether there are any other Grafanas as peers."""
        rel = self.model.get_relation(PEER)
        return len(rel.units) > 0 if rel is not None else False

    @property
    def peers(self):
        """Fetch the peer relation."""
        return self.model.get_relation(PEER)

    def set_peer_data(self, key: str, data: typing.Any) -> None:
        """Put information into the peer data bucket instead of `StoredState`."""
        if self.peers:
            self.peers.data[self.app][key] = json.dumps(data)

    def get_peer_data(self, key: str):
        """Retrieve information from the peer data bucket instead of `StoredState`."""
        if not self.peers:
            return {}
        data = self.peers.data[self.app].get(key, "")
        return json.loads(data) if data else {}

if __name__ == "__main__":  # pragma: nocover
    ops.main(CosMockCharm)  # type: ignore
