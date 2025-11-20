from typing import List, Tuple, Dict, Set, Optional, Any
import copy
from collections import defaultdict


class AirportCapabilityRules:
    """
    机场能力约束规则库
    """

    """1.机场状态约束规则"""
    @staticmethod
    def airport_open_check(airport, resources=None):
        """
        机场开放状态检查

        Args:
            airport: Airport对象
            resources: 资源字典（可选），包含：
                - airport_status: {airport_id: is_open} 机场开放状态映射

        Returns:
            bool: True表示机场开放，False表示机场关闭
        """
        # 方式1: 从Airport对象的属性读取（如果有is_open属性）
        if hasattr(airport, 'is_open'):
            is_open = airport.is_open
            status_source = "对象属性"
        # 方式2: 从resources字典读取
        elif resources and 'airport_status' in resources:
            is_open = resources['airport_status'].get(airport.id, True)  # 默认开放
            status_source = "资源配置"
        # 方式3: 默认开放
        else:
            is_open = True
            status_source = "默认值"

        airport_name = airport.name if hasattr(airport, 'name') and airport.name else f"机场{airport.id}"

        if is_open:
            print(f"    ✓ 机场状态检查: {airport_name} 开放 (来源: {status_source})")
        else:
            print(f"    ❌ 机场状态检查: {airport_name} 关闭 (来源: {status_source})")

        return is_open

    @staticmethod
    def update_airport_status(airport_id, is_open, resources):
        """
        更新机场开放状态（辅助方法）

        Args:
            airport_id: 机场ID
            is_open: 开放状态 (True/False)
            resources: 资源字典
        """
        if 'airport_status' not in resources:
            resources['airport_status'] = {}

        old_status = resources['airport_status'].get(airport_id, True)
        resources['airport_status'][airport_id] = is_open

        status_text = "开放" if is_open else "关闭"
        old_status_text = "开放" if old_status else "关闭"

        if old_status != is_open:
            print(f"    📝 机场状态更新: 机场{airport_id} {old_status_text} -> {status_text}")
        else:
            print(f"    📝 机场状态确认: 机场{airport_id} 保持{status_text}")

    """2.检查指控人员工作负荷约束规则"""
    @staticmethod
    def _check_airport_constraints(solution: Any, airport_id: int, drone_type: int,
                                   airports: Dict, target_drone_key: str) -> bool:
        """检查指控人员工作负荷约束是否满足"""
        airport = airports[airport_id]

        # 统计当前机场已使用的无人机（不包括目标无人机，因为它可能已经有任务）
        used_total = 0
        used_by_type = {}

        for key, tasks in solution.assignments.items():
            if tasks and key.startswith(f"{airport_id}_"):  # 有任务分配的无人机
                used_total += 1
                current_type = solution.drone_info[key]['type']
                used_by_type[current_type] = used_by_type.get(current_type, 0) + 1

        # 如果目标无人机还没有任务，需要检查添加它是否违反约束
        if target_drone_key not in solution.assignments or not solution.assignments[target_drone_key]:
            # 检查总数限制
            if hasattr(airport, 'total_limits') and used_total >= airport.total_limits:
                print(f"    ❌ 机场 {airport_id} 总数限制已达上限: {used_total}/{airport.total_limits}")
                return False

            # 检查类型限制
            current_type_used = used_by_type.get(drone_type, 0)
            type_limit = airport.type_limits.get(drone_type, 0) if hasattr(airport, 'type_limits') else 0
            if current_type_used >= type_limit:
                print(f"    ❌ 机场 {airport_id} 类型 {drone_type} 限制已达上限: {current_type_used}/{type_limit}")
                return False

        total_limits = airport.total_limits if hasattr(airport, 'total_limits') else 0
        type_limit = airport.type_limits.get(drone_type, 0) if hasattr(airport, 'type_limits') else 0
        
        print(f"    ✅ 机场 {airport_id} 约束检查通过: 总数 {used_total}/{total_limits}, "
              f"类型 {drone_type} {used_by_type.get(drone_type, 0)}/{type_limit}")
        return True

    """3.可用跑道数量约束规则"""
    @staticmethod
    def takeoff_runway_capacity(drone, task, event_time, resources):
        """
        起飞时的跑道容量约束检查

        Args:
            drone: Drone对象 - 需要起飞的无人机
            task: Task对象 - 执行的任务
            event_time: 起飞时间点
            resources: 资源字典，包含：
                - runway_counts: {airport_id: runway_count} 各机场跑道数量
                - runway_occupancy: {airport_id: [(start_time, end_time, drone_id, event_type), ...]} 跑道占用记录
                - takeoff_duration: float, 起飞占用跑道时长（分钟），默认5分钟

        Returns:
            bool: True表示有可用跑道，False表示跑道容量不足
        """
        if not hasattr(drone, 'airport') or drone.airport is None:
            print(f"    ❌ 无人机{drone.id if hasattr(drone, 'id') else '未知'}没有归属机场")
            return False

        airport = drone.airport
        airport_id = airport.id if hasattr(airport, 'id') else 'unknown'

        # 获取机场跑道数量
        runway_count = resources.get('runway_counts', {}).get(airport_id, 1)

        # 获取起飞占用时长
        takeoff_duration = resources.get('takeoff_duration', 5.0)

        # 计算起飞占用的时间窗口
        window_start = event_time
        window_end = event_time + takeoff_duration

        # 获取该机场的跑道占用记录
        runway_occupancy = resources.get('runway_occupancy', {}).get(airport_id, [])

        # 统计时间窗口内与当前起飞时间重叠的占用数量
        overlapping_count = 0
        for occupied_start, occupied_end, occupied_drone_id, event_type in runway_occupancy:
            # 检查时间段是否重叠: 只要不是完全不重叠就算重叠
            if not (window_end <= occupied_start or window_start >= occupied_end):
                overlapping_count += 1
                print(f"      重叠占用: 无人机{occupied_drone_id} {event_type} "
                      f"[{occupied_start:.2f}, {occupied_end:.2f}]")

        airport_name = airport.name if hasattr(airport, 'name') and airport.name else airport_id
        print(f"    机场{airport_name} 跑道总数: {runway_count}")
        print(f"    起飞时间窗口: [{window_start:.2f}, {window_end:.2f}] (持续{takeoff_duration}分钟)")
        print(f"    时间窗口内占用跑道数: {overlapping_count}/{runway_count}")

        # 检查是否还有可用跑道
        if overlapping_count >= runway_count:
            print(f"    ❌ 跑道容量不足: 所有跑道均被占用")
            return False

        available_runways = runway_count - overlapping_count
        print(f"    ✓ 跑道容量充足: 有 {available_runways} 条跑道可用")
        return True

    @staticmethod
    def landing_runway_capacity(drone, task, event_time, resources):
        """
        降落时的跑道容量约束检查

        Args:
            drone: Drone对象 - 需要降落的无人机
            task: Task对象 - 执行的任务
            event_time: 降落时间点
            resources: 资源字典，包含：
                - runway_counts: {airport_id: runway_count} 各机场跑道数量
                - runway_occupancy: {airport_id: [(start_time, end_time, drone_id, event_type), ...]} 跑道占用记录
                - landing_duration: float, 降落占用跑道时长（分钟），默认5分钟

        Returns:
            bool: True表示有可用跑道，False表示跑道容量不足
        """
        if not hasattr(drone, 'airport') or drone.airport is None:
            print(f"    ❌ 无人机{drone.id if hasattr(drone, 'id') else '未知'}没有归属机场")
            return False

        airport = drone.airport
        airport_id = airport.id if hasattr(airport, 'id') else 'unknown'

        # 获取机场跑道数量
        runway_count = resources.get('runway_counts', {}).get(airport_id, 1)

        # 获取降落占用时长
        landing_duration = resources.get('landing_duration', 5.0)

        # 计算降落占用的时间窗口
        window_start = event_time
        window_end = event_time + landing_duration

        # 获取该机场的跑道占用记录
        runway_occupancy = resources.get('runway_occupancy', {}).get(airport_id, [])

        # 统计时间窗口内与当前降落时间重叠的占用数量
        overlapping_count = 0
        for occupied_start, occupied_end, occupied_drone_id, event_type in runway_occupancy:
            # 检查时间段是否重叠
            if not (window_end <= occupied_start or window_start >= occupied_end):
                overlapping_count += 1
                print(f"      重叠占用: 无人机{occupied_drone_id} {event_type} "
                      f"[{occupied_start:.2f}, {occupied_end:.2f}]")

        airport_name = airport.name if hasattr(airport, 'name') and airport.name else airport_id
        print(f"    机场{airport_name} 跑道总数: {runway_count}")
        print(f"    降落时间窗口: [{window_start:.2f}, {window_end:.2f}] (持续{landing_duration}分钟)")
        print(f"    时间窗口内占用跑道数: {overlapping_count}/{runway_count}")

        # 检查是否还有可用跑道
        if overlapping_count >= runway_count:
            print(f"    ❌ 跑道容量不足: 所有跑道均被占用")
            return False

        available_runways = runway_count - overlapping_count
        print(f"    ✓ 跑道容量充足: 有 {available_runways} 条跑道可用")
        return True

    @staticmethod
    def update_runway_occupancy(airport_id, event_time, event_duration,
                                drone_id, event_type, resources):
        """
        更新跑道占用记录（辅助方法）

        Args:
            airport_id: 机场ID
            event_time: 事件开始时间
            event_duration: 事件持续时间
            drone_id: 无人机ID
            event_type: 事件类型 ('takeoff' 或 'landing')
            resources: 资源字典
        """
        if 'runway_occupancy' not in resources:
            resources['runway_occupancy'] = {}

        if airport_id not in resources['runway_occupancy']:
            resources['runway_occupancy'][airport_id] = []

        # 添加新的占用记录
        occupancy_record = (
            event_time,  # 开始时间
            event_time + event_duration,  # 结束时间
            drone_id,  # 无人机ID
            event_type  # 事件类型
        )
        resources['runway_occupancy'][airport_id].append(occupancy_record)

        print(f"    📝 记录跑道占用: 机场{airport_id} 无人机{drone_id} "
              f"{event_type} [{event_time:.2f}, {event_time + event_duration:.2f}]")

    """4.飞机数量约束规则"""
    @staticmethod
    def check_airport_q(drone, task, resources):
        """飞机数量约束规则"""

        # 检查每个型号数量限制
        type_available = min(
            resources['type_counts'].get(drone.type if hasattr(drone, 'type') else 'unknown', 0),
            resources['type_limits'].get(drone.type if hasattr(drone, 'type') else 'unknown', 0)
        )
        print(f"      类型可用数量: {type_available}")
        if type_available <= 0:
            print(f"      ❌ 类型配额不足")
            return False
        return True


class AircraftCapabilityRules:
    """飞机能力约束规则库"""

    """1.飞机类型约束"""
    @staticmethod
    def type_capacity(drone, task, resources):
        """飞机类型约束规则"""
        # 检查类型限制
        drone_type = drone.type if hasattr(drone, 'type') else 'unknown'
        required_types = task.required_types if hasattr(task, 'required_types') else []
        
        if drone_type not in required_types:
            print(f"      ❌ 类型不匹配: {drone_type} not in {required_types}")
            return False
        else:
            return True

    """2.有效载荷能力约束规则"""
    @staticmethod
    def payload_capacity(drone, task, resources):
        """有效载荷能力约束规则"""
        # 检查载荷匹配
        payload_match = True
        required_weapons = {}  # 记录需要的武器
        print(f"      载荷检查:")

        required_payloads = task.required_payloads if hasattr(task, 'required_payloads') else {}
        
        for payload_key, required_values in required_payloads.items():
            print(f"        检查载荷 {payload_key}: 需求{required_values}")

            if not hasattr(drone, 'payload_capability') or payload_key not in drone.payload_capability:
                print(f"          ❌ 无人机没有此载荷类型")
                payload_match = False
                break

            drone_range, drone_level = drone.payload_capability[payload_key]
            req_range, req_level = required_values
            print(f"          无人机载荷: 范围={drone_range}, 等级/数量={drone_level}")
            print(f"          需求: 范围≥{req_range}, 等级/数量≥{req_level}")

            if drone_range < req_range or drone_level < req_level:
                print(f"          ❌ 载荷能力不足")
                payload_match = False
                break

            # 如果是武器，记录需求
            if isinstance(payload_key, int) and payload_key == 1:  # 打击类
                required_weapons[payload_key] = req_level
                print(f"          武器需求记录: {payload_key} -> {req_level}")

        if not payload_match:
            print(f"      ❌ 载荷匹配失败")
            return False

        # 检查武器库存是否足够（只检查打击类），武器是消耗类，类型匹配也可能数量不足
        weapon_sufficient = True
        weapon_inventory = resources.get('weapon_inventory', {})
        
        for weapon_key, needed_count in required_weapons.items():
            available_count = weapon_inventory.get(weapon_key, 0)
            print(f"        武器库存检查 {weapon_key}: 需要{needed_count}, 可用{available_count}")
            if available_count < needed_count:
                weapon_sufficient = False
                print(f"          ❌ 武器库存不足")
                break

        if not weapon_sufficient:
            print(f"      ❌ 武器库存不足")
            return False

        return True

    """3.航程约束规则"""
    @staticmethod
    def range_constraint(drone, task, total_distance):
        """航程约束检查规则"""
        max_range = drone.max_range if hasattr(drone, 'max_range') else 0
        
        # 检查航程
        if total_distance > max_range:
            print(f"        ❌ 航程超限: {total_distance} > {max_range}")
            return False

        return True

    """4.速度约束规则"""
    @staticmethod
    def speed_constraint(drone, task):
        """速度约束检查规则"""
        cruise_speed = drone.cruise_speed if hasattr(drone, 'cruise_speed') else 0
        task_distance = task.distance if hasattr(task, 'distance') else 0
        task_max_duration = task.max_duration if hasattr(task, 'max_duration') else 0
        
        if task_max_duration <= 0:
            return True
            
        min_speed_required = task_distance / task_max_duration
        return cruise_speed >= min_speed_required

    """5.维修保养需求约束规则"""
    @staticmethod
    def effective_range_constraint(drone, resources):
        """
        维修保养需求约束规则；影响可用剩余航程。

        Args:
            drone: Drone对象 - 需要检查的无人机
            resources: 资源字典，包含：
                - maintenance_remaining: {drone_id: remaining_range} 各无人机距离下次大修的剩余里程(m)

        Returns:
            float: 有效最大航程（米），取max_range和剩余维修里程的较小值
        """
        # 获取无人机的最大航程
        max_range = drone.max_range if hasattr(drone, 'max_range') else float('inf')

        # 获取距离下次大修的剩余里程
        drone_id = drone.id if hasattr(drone, 'id') else 'unknown'
        maintenance_remaining = resources.get('maintenance_remaining', {}).get(drone_id, float('inf'))

        # 取两者较小值
        effective_range = min(max_range, maintenance_remaining)

        # 如果维修里程成为限制因素，给出提示
        if effective_range < max_range:
            print(f"    ⚠️  维修需求限制: 有效航程被维修里程约束")

        return effective_range


class TaskCharacteristicRules:
    """任务特性约束规则库"""

    """1.时间窗口约束规则"""
    @staticmethod
    def time_window_constraint(drone, task, distance):
        """时间窗口约束"""
        drone_speed = drone.speed if hasattr(drone, 'speed') else 0
        if drone_speed <= 0:
            print(f"        ❌ 无人机速度无效: {drone_speed}")
            return False
            
        # 单程飞行时间
        travel_time = distance / drone_speed
        # 最优起飞时间
        task_start = task.start_time if hasattr(task, 'start_time') else 0
        optimal_takeoff = task_start - travel_time
        # 实际起飞时间
        actual_takeoff = max(0.0, optimal_takeoff)
        # 实际到达时间
        earliest_arrival = actual_takeoff + travel_time
        print(f"        - 最优起飞时间: {optimal_takeoff:.2f}s")
        print(f"        - 实际起飞时间: {actual_takeoff:.2f}s")
        print(f"        - 最早到达时间: {earliest_arrival:.2f}s")
        
        task_end = task.end_time if hasattr(task, 'end_time') else float('inf')
        # 检查飞机能否在任务时间窗口内到达
        if earliest_arrival > task_end:
            print(f"        ❌ 无法在截止时间前到达")
            return False
            
        task_duration = task.duration if hasattr(task, 'duration') else 0
        # 检查飞机能否在截止时间前完成任务
        actual_start = max(earliest_arrival, task_start)
        if actual_start + task_duration > task_end:
            print(f"        ❌ 任务无法在截止时间前完成")
            return False
        return True


    """2.任务序列约束规则"""
    @staticmethod
    def check_drone_task_sequence(drone, task_ids: List[int], task_dict: Dict,
                                  distance_calculator) -> Dict[int, str]:
        """
        检查无人机任务序列的可行性（完全独立可用版本）

        这是一个完全独立的静态函数，内部自动创建和使用 SolutionChecker 的辅助方法。
        用户可以直接调用，无需任何额外的初始化工作。

        :param drone: 无人机对象（需要有 airport, type, speed, max_range, payload_capability 等属性）
        :param task_ids: 任务ID列表（按执行顺序）
        :param task_dict: 任务字典 {task_id: task_object}
        :param distance_calculator: 距离计算器对象
        :return: 字典 {task_id: status_string}，其中 status 为 "可行" 或错误描述

        使用示例：
            from drone_task_checker_standalone import check_drone_task_sequence

            # 直接调用即可！
            results = check_drone_task_sequence(
                drone=my_drone,
                task_ids=[1, 2, 3],
                task_dict=my_task_dict,
                distance_calculator=my_calculator
            )

            # 返回: {1: "可行", 2: "可行", 3: "航程超限..."}
        """
        # 导入并创建 SolutionChecker 实例（用于借用其辅助方法）
        try:
            from solution_checker import SolutionChecker
            checker = SolutionChecker()
            checker.task_dict = task_dict
            checker.distance_calculator = distance_calculator
        except ImportError:
            # 如果没有SolutionChecker，返回错误
            results = {}
            for task_id in task_ids:
                results[task_id] = "缺少SolutionChecker模块，无法检查任务序列"
            return results

        # ========== 以下是主逻辑 ==========
        results = {}

        if not task_ids:
            return results

        # 计算初始起飞时间
        try:
            optimal_takeoff = checker._calculate_optimal_takeoff_time(
                drone, task_ids[0] if task_ids else None
            )
        except Exception as e:
            optimal_takeoff = 0.0
            print(f"        ⚠️  无法计算最优起飞时间: {e}")

        # 初始化无人机状态
        current_location = ('airport', drone.airport.id) if hasattr(drone, 'airport') and hasattr(drone.airport, 'id') else ('airport', 'unknown')
        current_time = optimal_takeoff  # 使用计算出的最优起飞时间
        current_range = 0.0
        current_payload = copy.deepcopy(drone.payload_capability) if hasattr(drone, 'payload_capability') else {}

        for i, task_id in enumerate(task_ids):
            task = task_dict.get(task_id)
            if not task:
                results[task_id] = f"任务{task_id}不存在"
                # 如果当前任务不可行，后续任务也无法执行
                for j in range(i + 1, len(task_ids)):
                    future_task_id = task_ids[j]
                    results[future_task_id] = "前序任务不可行导致无法执行"
                break

            try:
                # 检查单个任务的可行性
                status = checker._check_single_task_feasibility(
                    drone, task, current_location, current_time,
                    current_range, current_payload, task_ids, i
                )
            except Exception as e:
                status = f"检查失败: {str(e)}"

            results[task_id] = status

            if status != "可行":
                # 如果当前任务不可行，后续任务也无法执行
                for j in range(i + 1, len(task_ids)):
                    future_task_id = task_ids[j]
                    results[future_task_id] = "前序任务不可行导致无法执行"
                break

            try:
                # 更新无人机状态（模拟执行当前任务）
                current_location, current_time, current_range = checker._simulate_task_execution(
                    drone, task, current_location, current_time, current_range
                )

                # 更新载荷状态
                checker._consume_task_payload(current_payload, task)
            except Exception as e:
                print(f"        ⚠️  更新无人机状态失败: {e}")
                results[task_id] = f"执行失败: {str(e)}"
                break

        return results

    """3.任务优先级约束规则"""
    @staticmethod
    def calculate_task_weight(task):
        """
        计算任务的权重值

        权重计算策略：
        - 优先级为主导因素（占70%权重）
        - 其他因素为辅助（持续时间、载荷、类型、带宽，共占30%）

        注意：优先级数字越小表示优先级越高（1=最高优先级，10=最低优先级）

        Args:
            task: Task对象，必须包含priority属性

        Returns:
            float: 任务权重值，越大表示优先级越高
        """
        # 1. 获取任务优先级（主导因素，占70%）
        if not hasattr(task, 'priority'):
            print(f"    ⚠️  任务{task.id if hasattr(task, 'id') else '未知'}缺少priority属性，使用默认值5")
            priority = 5
        else:
            priority = max(1, min(10, task.priority))  # 确保在1-10范围内

        # 优先级反向映射：1→70分，2→63分，...，10→7分
        priority_weight = (11 - priority) * 7.0

        # 2. 计算辅助因素（共占30%）
        task_duration = task.duration if hasattr(task, 'duration') else 0
        task_required_payloads = task.required_payloads if hasattr(task, 'required_payloads') else {}
        task_required_types = task.required_types if hasattr(task, 'required_types') else []
        task_bandwidth = task.bandwidth if hasattr(task, 'bandwidth') else 0

        # 2.1 持续时间因素（占6%）
        # 持续时间越长，权重略微增加（表示任务更重要/复杂）
        duration_hours = task_duration / 3600  # 转换为小时
        duration_weight = min(duration_hours * 0.3, 3.0)  # 最多加3分，避免过大

        # 2.2 载荷需求因素（占6%）
        # 载荷需求越多，权重略微增加
        payload_count = len(task_required_payloads) if task_required_payloads else 1
        payload_weight = min(payload_count * 0.6, 3.0)  # 最多加3分

        # 2.3 类型需求因素（占9%）
        # 类型需求越少（更灵活），权重略微增加
        type_count = len(task_required_types) if task_required_types else 1
        type_weight = 9.0 / type_count  # 1种类型=9分，2种=4.5分，3种=3分

        # 2.4 带宽需求因素（占9%）
        # 带宽需求越高，权重略微增加
        bandwidth_weight = min(task_bandwidth / 10.0 * 0.9, 9.0)  # 最多加9分

        # 3. 计算总权重
        total_weight = (priority_weight +
                        duration_weight +
                        payload_weight +
                        type_weight +
                        bandwidth_weight)

        task_name = task.name if hasattr(task, 'name') and task.name else f"任务{task.id if hasattr(task, 'id') else '未知'}"
        print(f"    {task_name} 权重计算:")
        print(f"      优先级权重: {priority_weight:.2f} (优先级{priority})")
        print(f"      持续时间权重: {duration_weight:.2f} ({duration_hours:.1f}h)")
        print(f"      载荷需求权重: {payload_weight:.2f} ({payload_count}种)")
        print(f"      类型需求权重: {type_weight:.2f} ({type_count}种)")
        print(f"      带宽需求权重: {bandwidth_weight:.2f} ({task_bandwidth})")
        print(f"      总权重: {total_weight:.2f}")

        return float(total_weight)

    @staticmethod
    def sort_tasks_by_weight(tasks):
        """
        按权重对任务列表排序

        Args:
            tasks: Task对象列表

        Returns:
            list: 按权重降序排列的任务列表（权重高的在前）
        """
        print(f"\n{'=' * 60}")
        print(f"📊 任务权重排序")
        print(f"{'=' * 60}")

        # 计算每个任务的权重
        task_weights = []
        for task in tasks:
            try:
                weight = TaskCharacteristicRules.calculate_task_weight(task)
                task_weights.append((weight, task))
            except Exception as e:
                print(f"    ⚠️  计算任务{task.id if hasattr(task, 'id') else '未知'}权重失败: {e}")
                task_weights.append((0.0, task))

        # 按权重降序排序
        task_weights.sort(key=lambda x: x[0], reverse=True)

        # 打印排序结果
        print(f"\n排序结果（共{len(tasks)}个任务）：")
        for rank, (weight, task) in enumerate(task_weights, 1):
            task_name = task.name if hasattr(task, 'name') and task.name else f"任务{task.id if hasattr(task, 'id') else '未知'}"
            priority = task.priority if hasattr(task, 'priority') else 5
            print(f"  {rank}. {task_name} - 权重{weight:.2f} (优先级{priority})")

        print(f"{'=' * 60}\n")

        # 返回排序后的任务列表
        return [task for weight, task in task_weights]

    @staticmethod
    def filter_high_priority_tasks(tasks, threshold=3):
        """
        筛选高优先级任务

        Args:
            tasks: Task对象列表
            threshold: 优先级阈值（默认3，表示优先级≤3的任务）
                      注意：数字越小优先级越高

        Returns:
            list: 高优先级任务列表
        """
        high_priority_tasks = []

        for task in tasks:
            if hasattr(task, 'priority'):
                priority = task.priority
            else:
                priority = 5  # 默认中等优先级

            if priority <= threshold:
                high_priority_tasks.append(task)

        print(f"    筛选出{len(high_priority_tasks)}个高优先级任务（优先级≤{threshold}）")

        return high_priority_tasks

    @staticmethod
    def get_task_priority_summary(tasks):
        """
        获取任务优先级分布统计（辅助方法）

        Args:
            tasks: Task对象列表

        Returns:
            dict: 优先级分布统计
        """
        priority_distribution = defaultdict(int)
        total_tasks = len(tasks)

        for task in tasks:
            if hasattr(task, 'priority'):
                priority = max(1, min(10, task.priority))
            else:
                priority = 5

            priority_distribution[priority] += 1

        print(f"\n{'=' * 60}")
        print(f"任务优先级分布统计")
        print(f"{'=' * 60}")
        print(f"总任务数: {total_tasks}\n")

        # 按优先级排序显示
        for priority in sorted(priority_distribution.keys()):
            count = priority_distribution[priority]
            percentage = (count / total_tasks) * 100 if total_tasks > 0 else 0
            bar = '█' * int(percentage / 5)  # 每5%一个方块
            print(f"  优先级{priority:2d}: {count:3d}个 ({percentage:5.1f}%) {bar}")

        print(f"{'=' * 60}\n")

        return dict(priority_distribution)


class GeographicalConstraintRules:
    """地理约束规则"""

    """1.通视条件约束"""
    @staticmethod
    def line_of_sight_check(position_geo, target_geo, dem, transform):
        """
        通视判定规则

        Args:
            position_geo: 阵位坐标 (lon, lat, elev)
            target_geo: 目标坐标 (lon, lat) 或 (lon, lat, elev)
            dem: DEM数据
            transform: 栅格变换矩阵

        Returns:
            bool: True表示通视，False表示不通视
        """
        try:
            from base_functions import geo_to_pixel_3d, line_of_sight_3d
        except ImportError:
            print(f"    ❌ 缺少base_functions模块，无法进行通视检查")
            return False

        pos_lon, pos_lat, pos_z = position_geo

        # 处理目标坐标（2D或3D）
        if len(target_geo) == 2:
            tar_lon, tar_lat = target_geo
            _, _, tar_z = geo_to_pixel_3d(tar_lon, tar_lat, transform, dem)
        else:
            tar_lon, tar_lat, tar_z = target_geo

        try:
            # 转换为栅格坐标
            pos_row, pos_col, _ = geo_to_pixel_3d(pos_lon, pos_lat, transform, dem)
            tar_row, tar_col, _ = geo_to_pixel_3d(tar_lon, tar_lat, transform, dem)

            # 通视检查
            is_visible = line_of_sight_3d(
                dem,
                (pos_row, pos_col, pos_z),
                (tar_row, tar_col, tar_z)
            )

            print(f"    通视检查: 阵位{(pos_lon, pos_lat)[:2]} -> 目标{(tar_lon, tar_lat)[:2]} "
                  f"{'✓ 通视' if is_visible else '✗ 不通视'}")
            return is_visible

        except Exception as e:
            print(f"    ❌ 通视检查异常: {e}")
            return False

    """2.飞行阵位选择规则"""
    @staticmethod
    def position_scoring(position_geo, target_geo, resources):
        """
        阵位评分规则（抵近目标 + 远离已占用阵位）

        评分因素：
        1. 距离目标越近，评分越高
        2. 距离已占用阵位越近，惩罚越大

        Args:
            position_geo: 阵位坐标 (lon, lat, elev)
            target_geo: 目标坐标 (lon, lat) 或 (lon, lat, elev) 或区域中心
            resources: 资源字典，包含：
                - occupied_positions: [(lon, lat, elev), ...] 已占用阵位列表
                - target_type: 'point' 或 'area'，默认'point'
                - coverage: 覆盖率（区域目标专用，0.0-1.0）

        Returns:
            float: 评分值，越高越好。不通视返回float('-inf')
        """
        try:
            from geopy.distance import geodesic
        except ImportError:
            print(f"    ❌ 缺少geopy模块，无法计算距离")
            return float('-inf')

        pos_lon, pos_lat, pos_z = position_geo

        # 提取目标位置（2D）
        if len(target_geo) == 2:
            tar_lon, tar_lat = target_geo
        else:
            tar_lon, tar_lat = target_geo[0], target_geo[1]

        # 1. 距离评分 - 距离越近评分越高
        distance_to_target = geodesic((pos_lat, pos_lon), (tar_lat, tar_lon)).meters

        target_type = resources.get('target_type', 'point')
        if target_type == 'area':
            # 区域目标：包含覆盖率评分
            coverage = resources.get('coverage', 0.0)
            coverage_score = coverage * 10000  # 覆盖率基础分
            distance_score = 50000 / (1 + distance_to_target)  # 距离评分
            base_score = coverage_score + distance_score
        else:
            # 点目标：仅距离评分
            distance_score = 100000 / (1 + distance_to_target)
            base_score = distance_score

        # 2. 阵位间距惩罚 - 距离已占用阵位越近惩罚越大
        position_penalty = 0
        occupied_positions = resources.get('occupied_positions', [])

        if occupied_positions:
            min_distance_to_occupied = float('inf')

            for occupied_pos in occupied_positions:
                occupied_lon, occupied_lat, _ = occupied_pos
                dist_to_occupied = geodesic((pos_lat, pos_lon), (occupied_lat, occupied_lon)).meters
                min_distance_to_occupied = min(min_distance_to_occupied, dist_to_occupied)

            # 20km范围内开始惩罚
            if min_distance_to_occupied < 20000:
                penalty_intensity = (20000 - min_distance_to_occupied) / 20000
                position_penalty = penalty_intensity * 50000

                # 5km范围内极重惩罚
                if min_distance_to_occupied < 5000:
                    position_penalty += 100000

            print(f"      最近已占用阵位距离: {min_distance_to_occupied:.0f}m, 惩罚: {position_penalty:.0f}")

        # 3. 总评分
        total_score = base_score - position_penalty

        print(f"    阵位评分: 距目标{distance_to_target:.0f}m, "
              f"基础分{base_score:.0f}, 总分{total_score:.0f}")

        return float(total_score)

    """3.安全阵位判断"""
    @staticmethod
    def threat_safety_check(position_geo, threats_geo, safety_buffer_m=5000):
        """
        威胁安全距离检查（硬约束）

        Args:
            position_geo: 阵位坐标 (lon, lat, elev)
            threats_geo: 威胁列表 [(lon, lat, type, radius_m), ...]
            safety_buffer_m: 安全缓冲距离，默认5000米

        Returns:
            bool: True表示安全，False表示太接近威胁
        """
        try:
            from base_functions import is_safe_from_threats
        except ImportError:
            print(f"    ❌ 缺少base_functions模块，无法进行威胁安全检查")
            return False

        is_safe = is_safe_from_threats(position_geo, threats_geo, safety_buffer_m)

        if not is_safe:
            print(f"    ❌ 威胁安全检查: 阵位{position_geo[:2]} 距离威胁过近")
        else:
            print(f"    ✓ 威胁安全检查: 阵位{position_geo[:2]} 安全")

        return is_safe


class EfficiencyOptimizationRules:
    """效率优化规则"""

    @staticmethod
    def total_distance_minimization(solution: Any):
        """
        总距离最小化（最短距离）
        """
        total_distance = 0
        
        # 检查必要的属性
        if not hasattr(solution, 'assignments'):
            print(f"    ❌ Solution对象缺少assignments属性")
            solution.metrics["total_distance"] = 0
            return
            
        for drone_key, task_ids in solution.assignments.items():
            if not task_ids:
                continue
                
            try:
                # 导入必要的模块
                from solution_checker import SolutionChecker
                checker = SolutionChecker()
                
                # 计算使用的航程和完成时间（基于最优起飞时间）
                final_location, final_time, total_range = checker.calculate_complete_route(
                    solution, drone_key, task_ids
                )
                total_distance += total_range
            except Exception as e:
                print(f"    ⚠️  计算无人机{drone_key}航程失败: {e}")
                continue
                
        if not hasattr(solution, 'metrics'):
            solution.metrics = {}
        solution.metrics["total_distance"] = total_distance


    @staticmethod
    def completion_time_minimization(solution: Any):
        """
        最大完成时间最小化(最短时间)
        """
        max_completion_time = 0
        
        # 检查必要的属性
        if not hasattr(solution, 'assignments'):
            print(f"    ❌ Solution对象缺少assignments属性")
            if hasattr(solution, 'metrics'):
                solution.metrics["completion_time"] = 0
            else:
                solution.metrics = {"completion_time": 0}
            return
            
        for drone_key, task_ids in solution.assignments.items():
            if not task_ids:
                continue
                
            try:
                # 导入必要的模块
                from solution_checker import SolutionChecker
                checker = SolutionChecker()
                
                # 计算使用的航程和完成时间（基于最优起飞时间）
                final_location, final_time, total_range = checker.calculate_complete_route(
                    solution, drone_key, task_ids
                )
                max_completion_time = max(max_completion_time, final_time)
            except Exception as e:
                print(f"    ⚠️  计算无人机{drone_key}完成时间失败: {e}")
                continue
                
        if not hasattr(solution, 'metrics'):
            solution.metrics = {}
        # 设置最大完成时间
        solution.metrics["completion_time"] = max_completion_time