import threading
import time
import concurrent.futures


def query_one_detail(val):
    time.sleep(2)
    current_thread = threading.current_thread()
    # print(current_thread.name + "|" + val)
    return val;


executor = concurrent.futures.ThreadPoolExecutor(max_workers=5);

# 计数器设置为任务数量

futures = []

if __name__ == '__main__':
    for index in range(100):
        # 提交任务给线程池
        future = executor.submit(query_one_detail, str(index))
        futures.append(future)

    # 提交完任务后，调用 shutdown 方法
    # executor.shutdown()

    for future in concurrent.futures.as_completed(futures):
        print(future.result())


    print("所有任务已完成")
