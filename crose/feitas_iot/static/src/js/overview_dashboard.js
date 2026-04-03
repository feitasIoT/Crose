/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

class OverviewDashboard extends Component {
    static template = "feitas_iot.OverviewDashboard";

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            components: [],
            overview: {
                stats: { agents: 0, instances: 0, topics: 0 },
                metrics: { cpu: "-", memory: "-", disk: "-", network: "-" },
                dashboard: {
                    connectivity: { topology: [], protocol: {} },
                    throughput: {},
                    value_delivery: { kpis: [], trend_points: [] },
                    asset_insight: {},
                },
            },
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const componentData = await rpc("/feitas_iot/get_component_status");
            this.state.components = componentData.components || [];
            if (componentData.overview) {
                this.state.overview = componentData.overview;
            }
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    getComponentStats(type) {
        const filtered = this.state.components.filter(c => c.component_type === type);
        const online = filtered.filter(c => c.status === 'online').length;
        const total = filtered.length;
        const pct = total > 0 ? Math.round((online * 100) / total) : 0;
        return { online, total, pct };
    }

    getTrendPath() {
        const points = (this.state.overview?.dashboard?.value_delivery?.trend_points) || [];
        if (!points.length) {
            return "";
        }
        const width = 340;
        const height = 110;
        const min = Math.min(...points);
        const max = Math.max(...points);
        const range = max - min || 1;
        return points.map((v, i) => {
            const x = points.length === 1 ? 0 : (i * width) / (points.length - 1);
            const y = height - ((v - min) / range) * height;
            return `${x},${y}`;
        }).join(" ");
    }

    getDeviceOnlinePct() {
        const asset = this.state.overview?.dashboard?.asset_insight || {};
        const total = Number(asset.devices_total || 0);
        const online = Number(asset.online_devices || 0);
        if (!total) {
            return 0;
        }
        return Math.round((online * 100) / total);
    }
}

registry.category("actions").add("feitas_iot.overview", OverviewDashboard);
