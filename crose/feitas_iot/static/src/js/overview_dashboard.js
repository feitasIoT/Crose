/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class OverviewDashboard extends Component {
    static template = "feitas_iot.OverviewDashboard";

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            components: [],
            stats: {},
            logs: [],
            overview: { stats: { agents: 0, instances: 0, topics: 0 } }
        });
        this.orm = useService("orm");

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        this.state.loading = true;
        try {
            const componentData = await rpc("/feitas_iot/get_component_status");
            this.state.components = componentData.components;
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
}

registry.category("actions").add("feitas_iot.overview", OverviewDashboard);
